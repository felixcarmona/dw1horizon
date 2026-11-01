#!/usr/bin/env python3
"""Build the everything disc with verified persistent artifacts; python3 -m tools.dev build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.build_cache import Cache, Capture, digest, key
from tools.derive import recipe


def run(cmd, env=None):
    subprocess.run(list(map(str, cmd)), cwd=ROOT, env=env, check=True)


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *map(str, args)], cwd=cwd, text=True).strip()


def prepare(tree):
    pin = git('rev-parse', 'HEAD:decomp')
    patches = sorted((ROOT / 'mods/patches').glob('*.patch'))
    signature = key([pin, [(p.name, digest(p)) for p in patches]])
    stamp = ROOT / 'build/dev-decomp.json'
    old = json.loads(stamp.read_text()) if stamp.exists() else {}
    if tree.exists() and old.get('signature') == signature:
        return
    if tree.exists():
        # The roster header is generated (tools/city_residents.py), never a user's edit.
        if (tree / 'src/main/city_residents_extra.h').exists():
            git('checkout', '--', 'src/main/city_residents_extra.h', cwd=tree)
        # Never reset a user's C edits while refreshing the patch series.
        status = git('status', '--porcelain', '--untracked-files=all', '--ignore-submodules=all', cwd=tree)
        edits = [line for line in status.splitlines() if not (
            line.startswith('?? ') and (line[3:] == 'text-bank-pad.json' or '__pycache__' in Path(line[3:]).parts))]
        if edits:
            raise RuntimeError(f'{tree}: commit/export local C edits and preserve untracked sources before refreshing the patch series')
        # A detached developer commit must remain reachable after tree refresh.
        head = git('rev-parse', 'HEAD', cwd=tree)
        run(['git', '-C', tree, 'update-ref', 'refs/dev-build/' + head, head])
        run(['git', '-C', ROOT / 'decomp', 'worktree', 'remove', '--force', tree])
    run(['git', '-C', ROOT / 'decomp', 'worktree', 'add', '--detach', tree, pin])
    run(['git', '-C', tree, '-c', 'user.name=Horizon authors', '-c', 'user.email=', 'am', '-q', *patches])
    seed = ROOT / 'decomp'
    for name in ('asm', 'build/us/psx/generated', 'external/psyq_headers'):
        if not (seed / name).is_dir():
            raise RuntimeError(f'missing {seed / name}; see docs/building.md (regenerate)')
        shutil.copytree(seed / name, tree / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
    stamp.write_text(json.dumps(dict(signature=signature)) + '\n')


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def extract(game, image, target, cache_dir):
    from tools.derive.importers.discs import extract_to
    inputs = [ROOT / 'tools/build_cache.py', Path(__file__), ROOT / 'tools/discs.py',
              ROOT / 'tools/derive/importers/discs.py']
    if game == 'dw1':
        inputs += [ROOT / 'tools/extract.sh', ROOT / '.tools/mkpsxiso/build/dumpsxiso']
    else:
        # release_files() reads this catalog, including its filename membership.
        inputs += sorted((ROOT / 'content/imports/releases').glob('*.json'))
    image_hash = sha1(image)
    if game == 'dw1':
        from tools.discs import DISCS
        if image_hash != DISCS[0]['sha1']:
            raise RuntimeError(f'{image}: native everything builds require the registered USA DW1 image')
    identity = dict(kind='extract', game=game, image_sha1=image_hash, target=str(target),
                    tools=[[str(p), digest(p)] for p in inputs])
    cache = Cache(cache_dir, ROOT) if cache_dir else None
    if cache and cache.restore(identity) is not None:
        print(f'extract {game}: verified cache hit', flush=True)
        return
    if game == 'dw1':
        run(['tools/extract.sh', image])
        outputs = [*target.rglob('*'), ROOT / 'build/digimonworld.xml']
    else:
        extract_to(game, image, target.parent)
        outputs = target.rglob('*')
    if cache:
        cap = Capture(ROOT)
        cap.writes = {str(p) for p in outputs if p.is_file() or p.is_dir()}
        cache.save(identity, cap, {'extracted': True})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lang', help='test build with only these languages (comma separated, include en)')
    p.add_argument('--no-cache', action='store_true', help='from-zero derived data and clean native compiles; bypass all caches')
    p.add_argument('--w', type=Path, help='use an already prepared private patched decomp tree')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--run', action='store_true', help='boot original-2-MB PCSX-Redux for --run-seconds, then stop it')
    p.add_argument('--run-seconds', type=int, default=60)
    p.add_argument('--name', default='dev-everything')
    p.add_argument('--dev-save', action='store_true', help="add the helper where talking to Jijimon opens the save machine (never on a player's disc)")
    a = p.parse_args(argv)
    if not a.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in a.name):
        p.error('--name must contain only letters, digits, - and _')
    if a.jobs < 1 or a.run_seconds < 1:
        p.error('jobs and run-seconds must be positive')
    os.chdir(ROOT)
    (ROOT / 'build').mkdir(exist_ok=True)
    # One driver per checkout: fresh staging must not race another build's writes.
    import fcntl
    with (ROOT / 'build/dev-build.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error('another developer build is running in this checkout')
        try:
            execute(a)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as e:
            raise SystemExit(str(e)) from e


def execute(a):
    out = ROOT / 'build' / a.name
    cache_dir = Path(os.environ.get('DW_CACHE_DIR', ROOT / 'build/cache')).expanduser().resolve()
    rec = recipe.load('everything')
    # Disc-dependent retouch paths are resolved only after private extraction.
    env = {k: v for k, v in os.environ.items() if k not in recipe.NOT_THE_RECIPES}
    for k, v in rec['environment'].items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    env.update(DWS_RELAYOUT='1', SCNASM_PACK_ASCII='1', PYTHONDONTWRITEBYTECODE='1')
    if a.dev_save:
        env['MAIN_STORY'] = 'tools/dws/examples/dev-save.dws'
    env.update(NAME=a.name, DERIVE_JOBS=str(a.jobs), REUSE_MODELS='0',
               DW_PORTRAITS_CACHE=str(out / 'derived/portraits-cache'))
    # Never inherit the old unchecked model reuse shortcut.
    if a.lang:
        from tools.languages import selected
        env['LANGS'] = '' if a.lang == 'en' else a.lang
        selected(env)  # validates language set and base
        if 'en' not in a.lang.split(','):
            raise RuntimeError('--lang test builds must include en (the on-disc overlay base)')
        print('TEST BUILD: selected languages only; not a release comparison', flush=True)
    if a.no_cache:
        env.pop('DW_BUILD_CACHE', None)
        env['DW_CLEAN_NATIVE'] = '1'
    else:
        env['DW_BUILD_CACHE'] = str(cache_dir)
    tree = a.w.expanduser().resolve() if a.w else ROOT / 'build/decomp-dev'
    env['W'] = str(tree)
    env['DW_CLEAN_NATIVE'] = '1'
    times = []
    start = time.monotonic()
    def stage(label, fn):
        t = time.monotonic()
        print(f'\n== dev {label}', flush=True)
        try:
            return fn()
        finally:
            times.append([label, round(time.monotonic() - t, 3)])
    if not a.w:
        stage('prepare decomp', lambda: prepare(tree))
    if not (tree / 'Makefile').exists():
        raise RuntimeError(f'missing prepared compiler tree: {tree}')
    # Python itself validates pyc by timestamps. Remove local bytecode before
    # running content-keyed tools so preserved source mtimes cannot hide edits.
    for base in ('tools', 'content', 'story'):
        for compiled in (ROOT / base).rglob('__pycache__'):
            shutil.rmtree(compiled)
    if a.no_cache:
        shutil.rmtree(tree / 'build/us/psx/gcc', ignore_errors=True)
    for directory in (out, Path(str(out) + '-maps'), ROOT / 'build/.cache-screen-pieces'):
        if directory.is_symlink():
            raise RuntimeError(f'refusing symlink output directory: {directory}')
        shutil.rmtree(directory, ignore_errors=True)
    extracted = ROOT / 'extracted'
    if extracted.is_symlink():
        raise RuntimeError('developer extraction requires a private extracted/ directory, not a symlink')
    shutil.rmtree(extracted, ignore_errors=True)
    isos = Path(os.environ.get('ISOS', 'build/isos/digimon-world')).expanduser()
    sources = Path(os.environ.get('SOURCE_ISOS', 'build/isos')).expanduser()
    images = [('dw1', Path(os.environ.get('DW1_US_IMAGE', isos / 'Digimon World (USA).bin')).expanduser(), extracted)]
    for game, var, default in (
        ('dcb', 'DCB_IMAGE', 'digital-card-battle/Digimon Digital Card Battle (USA).bin'),
        ('dw2', 'DW2_IMAGE', 'digimon-world-2/Digimon World 2 (USA).bin'),
        ('dw2003', 'DW3_IMAGE', 'digimon-world-2003/Digimon World 2003 (E) [SLES-03936].bin')):
        images.append((game, Path(os.environ.get(var, sources / default)).expanduser(), out / 'source-games' / game))
    for game, image, target in images:
        stage('extract ' + game, lambda g=game, i=image, t=target: extract(g, i, t, None if a.no_cache else cache_dir))
    env.update(recipe.env(rec, str(out), dev=False))
    stage('everything', lambda: run(['story/mods/what-the-island-forgot/build.sh'], env))
    report = dict(seconds=round(time.monotonic()-start, 3), stages=times, test_build=bool(a.lang),
                  cache=not a.no_cache, image_sha1=sha1(Path(str(out)+'.bin')))
    (ROOT / 'build' / (a.name + '-timings.json')).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)
    if a.run:
        # This command owns the emulator it starts, including interruption cleanup.
        emu = [sys.executable, 'tools/dev/emulator.py']
        port = os.environ.get('EMU_PORT', '39129')
        import socket
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', int(port)))
            except OSError as e:
                raise RuntimeError(f'emulator port {port} is already in use; choose EMU_PORT') from e
        emuenv = dict(env, EMU_PORT=port, EMU_ARGS='',
                      EMU_HOME=str(ROOT / 'build' / ('dev-emulator-home-' + port)))
        try:
            run([*emu, 'start', str(out)+'.cue'], emuenv)
            time.sleep(a.run_seconds)
        finally:
            run([*emu, 'stop'], emuenv)


if __name__ == '__main__':
    main()
