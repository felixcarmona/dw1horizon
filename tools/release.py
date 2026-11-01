#!/usr/bin/env python3
"""Build, verify, package and deploy Horizon. See docs/patcher.md#release-pipeline."""
import argparse
import contextlib
import datetime as dt
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAST = ('test_version', 'test_savecompat', 'test_pysum', 'test_derive_units',
        'test_patchbundle', 'test_patcher_reloc', 'test_release', 'test_release_reuse')


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', '-C', str(cwd), *args], text=True).strip()


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def python_cache(path):
    path = Path(path)
    return '__pycache__' in path.parts or path.suffix == '.pyc'


def pack_release(package, archive):
    """Keep runtime-generated Python caches out of player downloads."""
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(package, arcname='release-pkg',
                filter=lambda item: None if python_cache(item.name) else item)


def stop_group(process):
    """Stop a command and descendants, including a browser left after node fails."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def clean():
    status = git('status', '--porcelain', '--ignore-submodules=all')
    if status:
        raise RuntimeError('working tree must be clean (including untracked files):\n' + status)


def identity(tag):
    clean()
    import version
    info = version.describe(str(ROOT))
    if tag:
        ref = 'refs/tags/' + tag
        if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
            raise RuntimeError('tag must be an owner-created annotated vMAJOR.MINOR.PATCH')
        if git('cat-file', '-t', ref) != 'tag':
            raise RuntimeError(f'{tag}: release tag must be annotated')
        if git('rev-parse', ref + '^{commit}') != info['commit']:
            raise RuntimeError(f'HEAD must be exactly on {tag}')
        if info['version'] != tag[1:]:
            raise RuntimeError('version.py selected a different tag on HEAD')
    elif '-dev.' not in info['version']:
        raise RuntimeError('HEAD is a release: supply its tag explicitly, or move to a dev commit')
    return info


def record_key(release):
    """Fingerprint extraction inputs, derive inputs and recorder code.

    Patch/version metadata alone may reuse records. Regional mappings, readers,
    extraction lists and the selected builder can change dynamic graph reads.
    """
    h = hashlib.sha256()
    manifest = json.loads((release / 'manifest.json').read_text())
    variant = manifest.get('variants', {}).get(manifest.get('default'), {})
    context = {'bases': manifest['bases'], 'sources': manifest.get('source_discs'),
               'extract': manifest.get('extract'), 'local': variant.get('local'),
               'python': list(sys.version_info[:3]), 'implementation': sys.implementation.name,
               'platform': sys.platform}
    h.update(json.dumps(context, sort_keys=True).encode())
    # These readers perform extraction before the bundled derive jobs run.
    for path in sorted(release.glob('*.py')):
        h.update(b'reader/' + path.name.encode() + b'\0' + path.read_bytes())
    for label, base in (('bundle', release / 'bundle'), ('bases', release / 'bases'),
                        ('recorder', ROOT / 'web/enginebuild')):
        for path in sorted(base.rglob('*')):
            if path.is_file() and not python_cache(path):
                h.update(label.encode() + b'/' + str(path.relative_to(base)).encode()
                         + b'\0' + path.read_bytes())
    return h.hexdigest()


def offline_environment(recipe):
    """Toolchain regressions exercise the original defaults, not a disc recipe."""
    from tools.derive.recipe import NOT_THE_RECIPES
    env = dict(os.environ)
    for key in (*recipe['environment'], *NOT_THE_RECIPES, 'W', 'NAME', 'HEAP_OK',
                'MOD_VERSION', 'DERIVE_ARGS', 'SCREEN_CONTENT', 'DWS_MAPS',
                'EXTRA_STORY', 'EXTRA_FILES'):
        env.pop(key, None)
    return env


def selftest_fixtures(build):
    """Materialize default offline fixtures without borrowing a developer cache."""
    from tools.derive.importers import Provider, source_context
    from tools.dws import textx
    bank = ROOT / 'text/us/dialogue.json'
    bank.parent.mkdir(parents=True, exist_ok=True)
    textx.write_bank(textx.extract(), str(bank))
    copied = set()
    for folder in ('models', 'record-originals'):
        shutil.copytree(build / folder, ROOT / 'build' / folder, dirs_exist_ok=True)
        copied.update('build/' + folder + '/' + p.relative_to(build / folder).as_posix()
                      for p in (build / folder).rglob('*') if p.is_file())
    games = build / 'source-games'
    provider = Provider(games, build / 'selftest-imports')
    # The native imports already generated these exact legacy sources before
    # applying model deltas. Reuse only independently hash-verified bytes.
    for name, pin in provider.source_pins.items():
        for source in sorted((build / 'import-work').glob('*/' + name)):
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() == pin:
                provider.cache[name] = data
                break
    names = set()
    for source in (ROOT / 'content/species').glob('*.json'):
        species = json.loads(source.read_text())
        for kind in ('model', 'texture'):
            for field in ('file', 'partner_file'):
                name = species.get(kind, {}).get(field)
                if name and name.startswith('build/'):
                    names.add(name)
    with source_context(games):
        for name in sorted(names):
            target = ROOT / name
            if name in copied:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(provider.source(name))


class Run:
    def __init__(self, dry, out):
        self.dry, self.out = dry, out
        self.created = False
        self.times, self.sums = [], {}
        self.started = time.monotonic()

    @contextlib.contextmanager
    def step(self, name):
        print(f'\n== {name}', flush=True)
        start = time.monotonic()
        try:
            yield
        except BaseException:
            self.times.append((name, round(time.monotonic() - start, 2), 'FAILED'))
            raise
        else:
            self.times.append((name, round(time.monotonic() - start, 2),
                               'planned' if self.dry else 'ok'))

    def cmd(self, argv, env=None, cwd=ROOT):
        argv = list(map(str, argv))
        if env:
            print('Environment: ' + shlex.join(f'{k}={env[k]}' for k in
                  ('W', 'NAME', 'DW_HEAP_MAP', 'DERIVE_JOBS', 'RECORDS', 'ISOS', 'RELEASE', 'ENGINE', 'ENGINE_WORK') if k in env))
        print(shlex.join(argv), flush=True)
        if self.dry:
            return
        # A separate process group lets interruption stop docker/node/emu children too.
        p = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True)
        try:
            if p.wait():
                raise RuntimeError(f'command exited {p.returncode}: {shlex.join(argv)}')
        finally:
            # Also reap browsers left behind by a failed browser runner.
            stop_group(p)

    def summary(self, result):
        data = dict(result=result, seconds=round(time.monotonic() - self.started, 2),
                    steps=self.times, sha1=self.sums)
        print('\n' + json.dumps(data, indent=2), flush=True)
        if not self.dry and self.created:
            (self.out / 'summary.json').write_text(json.dumps(data, indent=2) + '\n')


def browser(r, out, engine, bases, sources, env):
    site = out / 'site'
    print(f'Prepare {site} with candidate engine; serve on an ephemeral localhost port')
    if r.dry:
        r.cmd(['node', 'web/test/run.mjs', 'http://127.0.0.1:PORT/?test=1',
               bases['us'], out / 'browser-profile', '2400'])
        print('Require done phase AND independent OPFS SHA-1 = manifest USA output')
        return
    shutil.copytree(ROOT / 'web', site, ignore=shutil.ignore_patterns('enginebuild', 'test', 'media'))
    (site / 'engine').symlink_to(engine, target_is_directory=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    benv = dict(env, BASES='us', OTHERS=';'.join(f'{k}={v}' for k, v in sources.items()))
    try:
        # suite.sh reports failures with exit 0: invoke its USA runner directly,
        # then parse the final JSON rather than trusting its exit alone.
        log = out / 'browser.log'
        script = ROOT / 'web/test/run.mjs'
        # Capture the runner's evidence for the explicit manifest comparison below.
        with log.open('w') as f:
            p = subprocess.Popen(['node', str(script),
                f'http://127.0.0.1:{server.server_port}/?test=1', str(bases['us']),
                str(out / 'browser-profile'), '2400'], env=benv, stdout=f,
                stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = p.wait(timeout=3000)
            finally:
                stop_group(p)
        if code:
            raise RuntimeError(f'USA browser failed; see {log}')
        text = log.read_text()
        start = text.index('{\n "phase"')
        result, _ = json.JSONDecoder().raw_decode(text[start:])
        manifest = json.loads((out / 'package/manifest.json').read_text())
        expected = manifest['variants'][manifest['default']]['outputs']['us']['sha1']
        if result['phase'] != 'done' or result['file']['sha1'] != expected:
            raise RuntimeError(f'USA browser output differs from release; see {log}')
        r.sums['browser-USA'] = result['file']['sha1']
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(out / 'browser-profile', ignore_errors=True)
        shutil.rmtree(site)


def pipeline(a, r):
    py = sys.executable
    with r.step('Clean tree and owner tag'):
        info = identity(a.tag)
        print(json.dumps(info))
        if a.publish and not a.tag:
            raise RuntimeError('--publish requires a release tag')
    with r.step('Published saves: mandatory file gate'):
        r.cmd([py, 'tools/dev/saves/releases.py', 'check'])
    with r.step('Fast offline regression tests'):
        for test in FAST:
            r.cmd([py, '-W', 'ignore::ResourceWarning', f'tools/{test}.py'])
    if a.preflight_only:
        return
    if a.prepare_reuse or a.reuse_from:
        import release_reuse
        if a.prepare_reuse:
            release_reuse.prepare(a, r, info)
        else:
            release_reuse.reuse(a, r, info)
        return
    isos = Path(os.environ.get('ISOS', 'build/isos/digimon-world')).expanduser()
    src = Path(os.environ.get('SOURCE_ISOS', 'build/isos')).expanduser()
    names = {'us': 'Digimon World (USA)', 'eu': 'Digimon World (Europe)',
             'fr': 'Digimon World (France)', 'de': 'Digimon World (Germany)',
             'es': 'Digimon World (Spain)', 'it': 'Digimon World (Italy)',
             'jp1': 'DigimonWorld (Japan) (Rev 1)'}
    bases = {k: Path(os.environ.get(f'DW1_{k.upper()}_IMAGE', isos / (v + '.bin'))).expanduser().resolve()
             for k, v in names.items()}
    sources = {k: Path(os.environ.get(var, src / default)).expanduser().resolve()
               for k, var, default in (
                   ('dcb', 'DCB_IMAGE', 'digital-card-battle/Digimon Digital Card Battle (USA).bin'),
                   ('dw2', 'DW2_IMAGE', 'digimon-world-2/Digimon World 2 (USA).bin'),
                   ('dw2003', 'DW3_IMAGE', 'digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin'))}
    out = r.out
    package, engine = out / 'package', out / 'engine'
    player_env = out / 'player-python'
    player_py = player_env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    w = out / 'decomp'
    common = Path(git('rev-parse', '--path-format=absolute', '--git-common-dir')).parent
    seed = Path(os.environ.get('DECOMP_REPO', common / 'decomp')).expanduser().resolve()
    pin = git('ls-tree', 'HEAD', 'decomp').split()[2]
    name = 'release-' + out.name
    build = ROOT / 'build' / name
    env = dict(os.environ)
    # Never inherit developer byte overrides or a heap bypass into a release.
    from tools.derive.recipe import NOT_THE_RECIPES
    for key in (*NOT_THE_RECIPES, 'HEAP_OK', 'MOD_VERSION', 'DEV', 'EXTRA_SPECIES', 'DERIVE_ARGS',
                'DW_BUILD_CACHE', 'DW_CLEAN_NATIVE'):
        env.pop(key, None)
    recipe = json.loads((ROOT / 'tools/derive/recipes/everything.json').read_text())
    for key, value in recipe['environment'].items():
        if value is None:
            env.pop(key, None)
    env.update({k: str(v) for k, v in recipe['environment'].items() if v is not None})
    env.update(W=str(w), NAME=name, DERIVE_JOBS=str(a.jobs), REUSE_MODELS='0',
               DW_PORTRAITS_CACHE=str(build / 'derived/portraits-cache'))
    with r.step('Prerequisites and ten input SHA-1s'):
        if not r.dry:
            if out.exists():
                raise RuntimeError(f'output must be a new folder: {out}')
            if build.exists() or Path(str(build) + '.bin').exists():
                raise RuntimeError(f'native build name already exists: {build}; choose another --out basename')
            for p in (*bases.values(), *sources.values(), ROOT / 'extracted/SLUS_010.32',
                      ROOT / '.tools/mkpsxiso/build/mkpsxiso', ROOT / 'build/digimonworld.xml', seed / 'asm',
                      ROOT / 'decomp/config/us/symbols.txt',
                      seed / 'build/us/psx/generated', seed / 'external/psyq_headers'):
                if not p.exists():
                    raise RuntimeError(f'missing prerequisite: {p}; see patcher.md §12')
            if git('rev-parse', '--show-toplevel', cwd=seed) != str(seed):
                raise RuntimeError('DECOMP_REPO must be the decomp repository')
            for k, p in {**bases, **sources}.items():
                r.sums[f'input-{k}: {p}'] = sha1(p)
            from discs import DISCS, DW1_RELEASES, SOURCE_DISCS
            expected = {'us': DISCS[0]['sha1'], **{d['id'][4:]: d['sha1']
                        for d in DW1_RELEASES if d['supported']},
                        **{d['id']: d['sha1'] for d in SOURCE_DISCS}}
            for k, path in {**bases, **sources}.items():
                if r.sums[f'input-{k}: {path}'] != expected[k]:
                    raise RuntimeError(f'{k}: input SHA-1 differs from registered source: {path}')
            for rel, expected_sha in DISCS[0]['files'].items():
                if sha1(ROOT / 'extracted' / rel) != expected_sha:
                    raise RuntimeError(f'extracted/{rel} is not from the USA source disc')
            out.mkdir(parents=True)
            r.created = True
    with r.step('Isolated Python for standalone player gates'):
        r.cmd([py, '-m', 'venv', '--without-pip', player_env])
    with r.step('Private decomp worktree, pinned base and full patch series'):
        r.cmd(['git', '-C', seed, 'worktree', 'add', '--detach', w, pin])
        r.cmd(['git', '-C', w, '-c', 'user.name=Horizon authors', '-c', 'user.email=',
               'am', *sorted((ROOT / 'mods/patches').glob('*.patch'))])
        if not r.dry:
            for rel in ('asm', 'build/us/psx/generated', 'external/psyq_headers'):
                shutil.copytree(seed / rel, w / rel, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('.git'))
    with r.step('Source disc extraction for native imports'):
        cmd = [py, '-m', 'tools.derive', 'sources', '--out', build / 'source-games']
        for k, p in sources.items():
            cmd += ['--source-disc', f'{k}={p}']
        r.cmd(cmd, env)
    with r.step('Build everything disc (original 2 MB hardware)'):
        r.cmd(['story/mods/what-the-island-forgot/build.sh'], env)
    elfmap = w / 'build/us/psx/gcc/SLUS_010.32.elf.map'
    with r.step('Executable heapcheck'):
        r.cmd([py, 'tools/heapcheck.py', elfmap], env)
    with r.step('Story heap check with final executable map'):
        from tools.derive import recipe as recipes
        checkenv = dict(env, **({} if r.dry else recipes.env(recipe, str(build))), DW_HEAP_MAP=str(elfmap),
                        DW_MODEL_ARCHIVE=str(build / 'DIGI.DAT'), DW_EXE_FACTS=str(build / 'derived/exe-facts.json'),
                        DWS_RELAYOUT='1', SCNASM_PACK_ASCII='1')
        facts = {} if r.dry else json.loads((build / 'derived/exe-facts.json').read_text())
        target = ['--ground-pickup-max', str(facts.get('ground_pickup_max') or 0),
                  '--maphead-max', str(facts.get('maphead_script_max') or 0x6800),
                  '--font-glyphs', str(facts.get('font_glyphs') or 0),
                  '--exe-font', facts.get('makefile_font') or 'original']
        if r.dry:
            print('Story buffer/font arguments below are placeholders; real run reads final derived/exe-facts.json')
        r.cmd([py, 'tools/dws.py', 'story-build', *recipe['story']['sources'], '--mods', 'all', '--read-only-locks',
               '--exe', 'mods', '--imported-npcs', '--exe-dir', w / 'build/us/psx/gcc',
               *target, '-o', out / 'story-check/DG.SCN'], checkenv)
    with r.step('Prepare source-derived fixtures for offline selftest'):
        # Original-content regressions resolve these declared paths, independently
        # of the everything recipe's model provider and output directory.
        if not r.dry:
            selftest_fixtures(build)
    with r.step('Toolchain selftest (offline release gate)'):
        testenv = offline_environment(recipe)
        testenv['DW_SELFTEST_DERIVE'] = str(build)
        r.cmd(['tools/selftest.sh'], testenv)
    with r.step('Package seven bases and three sources; mandatory save gate'):
        cmd = [py, 'tools/patcher/dwpatch.py', 'make-release', '--original', bases['us'],
               '--variant', f'everything={build}.bin', '--title', 'Digimon World Horizon', '-o', package]
        for k, p in bases.items():
            if k != 'us':
                cmd += ['--base', f'{k}={p}']
        for k, p in sources.items():
            cmd += ['--source-disc', f'{k}={p}']
        if a.save_check_emu:
            cmd += ['--save-check-emu']
        r.cmd(cmd, env)
        if not r.dry:
            manifest = json.loads((package / 'manifest.json').read_text())
            for k, output in manifest['variants'][manifest['default']]['outputs'].items():
                r.sums['output-' + k] = output['sha1']
    with r.step('Standalone package apply (USA and Japan Rev 1)'):
        for base in ('us', 'jp1'):
            dest = out / ('standalone-' + base)
            # Run the shipped reader outside the checkout, without developer imports.
            standalone_env = dict(env)
            for key in ('PYTHONPATH', 'PYTHONHOME'):
                standalone_env.pop(key, None)
            standalone_env.update(PYTHONNOUSERSITE='1', VIRTUAL_ENV=str(player_env),
                                  PATH=str(player_py.parent) + os.pathsep + standalone_env.get('PATH', ''))
            cmd = [player_py, '-B', '-E', '-S', package / 'dwpatch.py', 'apply', bases[base], '-o', dest]
            for key, path in sources.items():
                cmd += ['--source-disc', f'{key}={path}']
            r.cmd(cmd, standalone_env, cwd=out)
            if not r.dry:
                images = list(dest.glob('*.bin'))
                expected = manifest['variants'][manifest['default']]['outputs'][base]['sha1']
                if len(images) != 1 or sha1(images[0]) != expected:
                    raise RuntimeError(f'{base}: standalone image differs from package manifest')
                r.sums['standalone-' + base] = expected
                shutil.rmtree(dest)
        if not r.dry:
            shutil.rmtree(player_env)
    if a.record_save:
        with r.step('Record this release save in a private corpus copy'):
            corpus = out / 'save-corpus'
            if not r.dry:
                shutil.copytree(ROOT / 'tools/dev/saves/corpus', corpus)
            r.cmd([py, 'tools/dev/saves/releases.py', 'add', str(build) + '.cue',
                   '--exe', build / 'exe/SLUS_010.32', '--corpus', corpus,
                   '--name', info['version'] + '-' + info['commit'][:8],
                   '--version', info['version'], '--commit', info['commit'],
                   '--date', info['date'], '--from', a.record_save,
                   '--work', out / 'save-recording'], env)
    with r.step('Engine graph fingerprint and record reuse'):
        cache = ROOT / 'build/release-records'
        key = '<bundle-and-recorder-SHA256>' if r.dry else record_key(package)
        records = cache / key
        print(f'RECORDS={records} (reuse only for identical graph inputs)')
        # build-engine.sh uses fixed filenames under ISOS; give it a private directory.
        alias = out / 'base-discs'
        if not r.dry:
            alias.mkdir()
            for k, p in bases.items():
                (alias / (names[k] + '.bin')).symlink_to(p)
        webenv = dict(env, RECORDS=str(records), ISOS=str(alias), ENGINE_WORK=str(out / 'engine-work'),
                      DCB_IMAGE=str(sources['dcb']), DW2_IMAGE=str(sources['dw2']),
                      DW3_IMAGE=str(sources['dw2003']))
        r.cmd(['web/build-engine.sh', package, engine], webenv)
    if not a.skip_browser:
        with r.step('USA browser suite on candidate before deployment'):
            browser(r, out, engine, bases, sources, env)
    else:
        r.times.append(('USA browser suite (--skip-browser)', 0, 'SKIPPED'))
    with r.step('Pack release (package only, never images) and SHA-1 inventory'):
        archive = out / ('horizon-' + info['version'] + '.tar.gz')
        if not r.dry:
            pack_release(package, archive)
            for p in [Path(str(build) + '.bin'), archive, *sorted(package.rglob('*')),
                      *sorted(engine.rglob('*'))]:
                if p.is_file() and not python_cache(p):
                    r.sums[str(p)] = sha1(p)
    with r.step('Verify checkout still names the built commit'):
        if not r.dry and identity(a.tag) != info:
            raise RuntimeError('checkout or version changed during build')
    if a.deploy:
        with r.step('Deploy candidate engine and page'):
            r.cmd(['web/deploy.sh'], dict(env, RELEASE=str(package), ENGINE=str(engine)))
    if a.publish:
        with r.step('Push owner tag and create GitHub release'):
            r.cmd(['git', 'push', a.remote, f'refs/tags/{a.tag}:refs/tags/{a.tag}'])
            r.cmd(['gh', 'release', 'create', a.tag, archive, '--verify-tag',
                   '--title', 'Digimon World Horizon ' + info['version'],
                   '--notes-file', a.notes_file])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tag', nargs='?', help='existing annotated owner tag; omit for dev')
    p.add_argument('--dry-run', action='store_true', help='print commands; no builds, writes or deployment')
    p.add_argument('--preflight-only', action='store_true', help='clean/tag, save file gate and fast tests only')
    p.add_argument('--save-check-emu', action='store_true')
    p.add_argument('--record-save', type=Path, metavar='SEED.mcd',
                   help='also run releases.py add into OUT/save-corpus (emulator; owner commits the new pair later)')
    p.add_argument('--skip-browser', action='store_true')
    p.add_argument('--deploy', action='store_true', help='deploy to the configured server (off by default)')
    p.add_argument('--publish', action='store_true', help='push tag and gh release create (off by default)')
    p.add_argument('--remote', default='origin')
    p.add_argument('--notes-file', type=Path)
    p.add_argument('--jobs', type=int, default=4)
    reuse = p.add_mutually_exclusive_group()
    reuse.add_argument('--prepare-reuse', action='store_true',
                       help='seal an existing final proof before tagging (no builds)')
    reuse.add_argument('--reuse-from', type=Path, metavar='HANDOFF',
                       help='reuse a sealed final proof from exactly the same git tree')
    for name in ('package', 'outputs', 'build', 'engine', 'bases', 'sources'):
        p.add_argument('--reuse-' + name, type=Path,
                       help='prepare-reuse input (' + name + '; bases/sources are KEY:PATH JSON)')
    p.add_argument('--out', type=Path, default=ROOT / 'build/releases' / dt.datetime.now(
        dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    a = p.parse_args(argv)
    if a.jobs < 1:
        p.error('--jobs must be positive')
    if a.prepare_reuse and any(getattr(a, 'reuse_' + name) is None for name in
                              ('package', 'outputs', 'build', 'engine', 'bases', 'sources')):
        p.error('--prepare-reuse requires --reuse-{package,outputs,build,engine,bases,sources}')
    if not a.prepare_reuse and any(getattr(a, 'reuse_' + name) is not None for name in
                                   ('package', 'outputs', 'build', 'engine', 'bases', 'sources')):
        p.error('--reuse-* inputs belong to --prepare-reuse')
    if a.reuse_from:
        a.reuse_from = a.reuse_from.expanduser().resolve()
    if a.notes_file:
        a.notes_file = a.notes_file.expanduser().resolve()
    if a.publish and (not a.tag or not a.notes_file or not a.notes_file.is_file()):
        p.error('--publish requires tag and an existing --notes-file')
    if a.record_save:
        a.record_save = a.record_save.expanduser().resolve()
        if not a.record_save.is_file():
            p.error('--record-save seed does not exist')
    r = Run(a.dry_run, a.out.expanduser().resolve())
    result = 'ok'
    try:
        pipeline(a, r)
    except (Exception, KeyboardInterrupt) as e:
        result = f'FAILED: {e}'
        print(result, file=sys.stderr)
    finally:
        r.summary(result)
    return 0 if result == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
