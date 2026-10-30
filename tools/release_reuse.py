"""Checksum-bound release handoff and fixed-size version restamping. No builders."""
import copy
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/patcher'))
import dwpatch as dw
import isowriter as iw

BASES = {'us', 'eu', 'fr', 'de', 'es', 'it', 'jp1'}
EXE = 'SLUS_010.32'


def digest(data):
    return hashlib.sha1(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def inventory(folder):
    import release
    result = {}
    for path in sorted(Path(folder).rglob('*')):
        if path.is_symlink():
            raise RuntimeError(f'reuse artifact must not contain symlinks: {path}')
        if path.is_file() and not release.python_cache(path):
            result[str(path.relative_to(folder))] = release.sha1(path)
    return result


def require_equal(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f'reuse refused: {label} mismatch')


def version_bytes(version):
    import version as versions
    text = versions.game_text({'version': version}).encode('ascii')
    if not re.fullmatch(rb'[0-9A-Za-z.+-]{1,31}', text):
        raise RuntimeError('invalid title version')
    return text.ljust(32, b'\0')


def version_offset(mapfile):
    matches = re.findall(r'^\s+(0x[0-9a-fA-F]+)\s+MOD_VERSION_TEXT\s*$', Path(mapfile).read_text(), re.M)
    if len(matches) != 1:
        raise RuntimeError('reuse requires exactly one MOD_VERSION_TEXT linker symbol')
    return int(matches[0], 16) - 0x80090000


def stamp(data, offset, old, new):
    if offset < 0 or offset + 32 > len(data):
        raise RuntimeError('version symbol outside executable')
    require_equal(data[offset:offset + 32], version_bytes(old), 'executable version buffer')
    return data[:offset] + version_bytes(new) + data[offset + 32:]


def retarget_delta(entry, blob, originals, target):
    """Recompute controls' diff/extra blocks against each original source.

    Keep the verified alignment; no suffix search and no stale version bytes.
    Copy-on-write blocks also handle deduplicated extents in the old payload.
    """
    entry = copy.deepcopy(entry)
    result = bytearray(blob)
    for base, delta in entry['bases'].items():
        source = originals[base].read(delta['source'])
        require_equal(digest(source), delta['source_sha1'], base + ' delta source')
        diff, extra = bytearray(), bytearray()
        oldpos = newpos = 0
        for n, count, seek in delta['control']:
            if min(n, count) < 0 or newpos + n + count > len(target):
                raise RuntimeError('invalid reusable delta control')
            for i in range(n):
                at = oldpos + i
                diff.append((target[newpos + i] - (source[at] if 0 <= at < len(source) else 0)) & 255)
            extra.extend(target[newpos + n:newpos + n + count])
            oldpos += n + seek
            newpos += n + count
        require_equal(newpos, len(target), 'delta target size')
        delta['diff'] = [len(result), len(diff)]
        result.extend(diff)
        delta['extra'] = [len(result), len(extra)]
        result.extend(extra)
    entry.update(sha1=digest(target), size=len(target))
    for base, image in originals.items():
        require_equal(dw.apply_binary_delta(entry, base, image.read, result), target, base + ' restamped delta')
    return entry, bytes(result)


def compact(payload):
    """Drop all superseded blocks, including the previous version stamp."""
    blob = payload['blob']
    out, spans = bytearray(), {}
    def move(pair):
        key = tuple(pair)
        if key not in spans:
            at, length = pair
            if min(at, length) < 0 or at + length > len(blob):
                raise RuntimeError('invalid payload extent')
            spans[key] = [len(out), length]
            out.extend(blob[at:at + length])
        return list(spans[key])
    for ops in [*payload['files'].values(), payload['license']]:
        for op in ops:
            if op[0] == 'l':
                op[1:3] = move(op[1:3])
    for entry in payload.get('deltas', []):
        for delta in entry['bases'].values():
            for block in ('diff', 'extra'):
                delta[block] = move(delta[block])
    payload['blob'] = bytes(out)


def restamp_payload(payload, originals, offset, old, new):
    ops = payload['files'][EXE]
    if len(ops) != 1 or ops[0][0] != 'b' or ops[0][2] != 0:
        raise RuntimeError('reuse requires a whole-file executable binary delta')
    index = ops[0][1]
    # Other file operations must not inherit the changed buffer through reuse.
    for file, other in payload['files'].items():
        if file == EXE:
            continue
        for op in other:
            if ((op[0] == 'b' and op[1] == index) or
                    (op[0] == 'o' and op[1] == EXE and
                     op[2] < offset + 32 and op[2] + op[3] > offset)):
                raise RuntimeError('version bytes are reused by another file; full build required')
    entry = payload['deltas'][index]
    require_equal(entry['file'], EXE, 'executable delta file')
    require_equal(ops[0][3], entry['size'], 'executable delta length')
    target = dw.apply_binary_delta(entry, 'us', originals['us'].read, payload['blob'])
    for base, image in originals.items():
        require_equal(dw.apply_binary_delta(entry, base, image.read, payload['blob']), target, base + ' old delta')
    target = stamp(target, offset, old, new)
    payload['deltas'][index], payload['blob'] = retarget_delta(entry, payload['blob'], originals, target)
    payload['sha1'][EXE] = digest(target)
    compact(payload)
    return payload


def save_payload(path, payload):
    metadata = dict(payload)
    blob = metadata.pop('blob')
    encoded = json.dumps(metadata, separators=(',', ':')).encode()
    Path(path).write_bytes(lzma.compress(b'DWP3' + struct.pack('<I', len(encoded)) + encoded + blob,
                                       preset=9 | lzma.PRESET_EXTREME))


def file_sums(path):
    image = iw.Image(str(path))
    try:
        return {**{name: digest(image.read(name)) for name in image.files},
                '@license': digest(image.license())}
    finally:
        image.f.close()


def verify_outputs(package, images, bases, sources):
    """Stream each shipped writer result to a hash sink, using verified holes.

    This replays no derive job and writes no temporary disc. It catches table
    rewrites, reused output ranges and regional mapping mistakes as well as deltas.
    """
    manifest = read(package / 'manifest.json')
    variant = manifest['variants']['everything']
    payload = dw.read_payload3(dw.read_patch_file(str(package), variant))
    class Sink:
        def write(self, data):
            return len(data)
    for key, original in bases.items():
        image = iw.Image(str(images / f'everything-{key}.bin'))
        try:
            holes = {}
            for hole in variant['holes']:
                data = image.read(hole['file'])
                require_equal(len(data), hole['size'], key + ' hole size')
                require_equal(digest(data), hole.get('sha1_by_base', {}).get(key, hole['sha1']), key + ' hole SHA-1')
                holes[hole['id']] = data
            mapping = manifest['bases'][key].get('mapping')
            with tempfile.TemporaryDirectory(prefix='reuse-writer-') as work:
                base = dw.BaseDisc(key, str(original), read(package / mapping) if mapping else None,
                    tool_root=str(package / 'bundle'), work=work,
                    source_discs=[f'{k}={p}' for k, p in sources.items()])
                try:
                    sha, _ = dw.build_disc3(payload, base, holes, Sink(), progress=False)
                    require_equal(sha, variant['outputs'][key]['sha1'], key + ' streamed package output')
                finally:
                    base.img.f.close()
        finally:
            image.f.close()


def restamp_image(source, dest, offset, old, new):
    """Change only the version buffer and its raw Form 1 EDC/ECC bytes."""
    image = iw.Image(str(source))
    try:
        original = image.read(EXE)
        target = stamp(original, offset, old, new)
        lba, size, xa = image.files[EXE]
        if xa:
            raise RuntimeError('executable is not Form 1 data')
        shutil.copyfile(source, dest)
        with Path(dest).open('r+b') as output:
            for k in range(offset // iw.DATA, (offset + 31) // iw.DATA + 1):
                raw = image.raw(lba + k)
                sector = bytearray(raw[24:24 + iw.DATA])
                start = k * iw.DATA
                sector[:min(iw.DATA, size - start)] = target[start:start + iw.DATA]
                output.seek((lba + k) * iw.RAW)
                output.write(iw.form1(lba + k, raw[16:24], bytes(sector)))
    finally:
        image.f.close()
    before, after = file_sums(source), file_sums(dest)
    expected = dict(before, **{EXE: digest(target)})
    require_equal(after, expected, 'all disc-file/license sums after restamp')
    return dict(before=before, after=after)


def unpack_engine_file(stage, plan, row):
    name, pack, offset, stored, size, method = row
    with (stage / 'packs' / plan['packs'][pack]['name']).open('rb') as source:
        source.seek(offset)
        data = source.read(stored)
    if method == 8:
        data = zlib.decompress(data, -15)
    elif method != 0:
        raise RuntimeError('unknown engine pack compression')
    require_equal(len(data), size, 'engine file size ' + name)
    return data


def engine_package(engine, package):
    """Require every embedded release file to name this exact package."""
    current = read(engine / 'current.json')
    stage = engine / current['version']
    plan = read(stage / 'plan.json')
    import release
    for pack in plan['packs']:
        require_equal(release.sha1(stage / 'packs' / pack['name']), pack['sha1'], 'engine pack')
    names = set()
    for row in plan['files']:
        if row[0].startswith('.release/'):
            name = row[0][9:]
            require_equal(unpack_engine_file(stage, plan, row), (package / name).read_bytes(), 'engine package ' + name)
            names.add(name)
    manifest = read(package / 'manifest.json')
    variant = manifest['variants'][manifest['default']]
    if not {'manifest.json', variant['patch'], 'dwpatch.py', 'isowriter.py'} <= names:
        raise RuntimeError('engine lacks required release files')
    require_equal(plan['release']['outputs'], variant['outputs'], 'engine outputs')
    return stage, plan


def repack_engine(source, dest, package):
    """Reuse the graph and vendor runtime, repack only changed release files."""
    current = read(source / 'current.json')
    old = source / current['version']
    plan = read(old / 'plan.json')
    stage = dest / 'stage'
    shutil.copytree(old, stage)
    rows = []
    for i, pack in enumerate(plan['packs']):
        offset = 0
        with (stage / 'packs' / pack['name']).open('wb') as output:
            for row in (r for r in plan['files'] if r[1] == i):
                name = row[0]
                data = ((package / name[9:]).read_bytes() if name.startswith('.release/')
                        else unpack_engine_file(old, plan, row))
                compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
                compressed = compressor.compress(data) + compressor.flush()
                method = 8 if len(compressed) < len(data) * .97 else 0
                stored = compressed if method else data
                output.write(stored)
                rows.append([name, i, offset, len(stored), len(data), method])
                offset += len(stored)
        import release
        pack.update(size=offset, sha1=release.sha1(stage / 'packs' / pack['name']))
    manifest = read(package / 'manifest.json')
    plan['files'] = rows
    plan['release'].update(version=manifest['version'], commit=manifest['commit'],
                           outputs=manifest['variants'][manifest['default']]['outputs'])
    text = json.dumps(plan, separators=(',', ':'))
    version = digest(text.encode() + b''.join(p['sha1'].encode() for p in plan['packs']))[:12]
    (stage / 'plan.json').write_text(text)
    stage.rename(dest / version)
    write(dest / 'current.json', dict(version=version, release=manifest['version'], commit=manifest['commit'],
                                     release_version=manifest['version'], release_date=manifest['date']))
    engine_package(dest, package)


def audit_build_files(build):
    paths = set(build.glob('exe*/SLUS_010.32.elf.map'))
    paths.update(build.glob('text-bank-*.json'))
    paths.update((build / 'lang').glob('*'))
    paths.update([build / 'derived/manifest.json', build / 'derived/plan.json'])
    return sorted(p for p in paths if p.is_file())


def publication(package, build, bases, sources):
    import literal_gate
    manifest = read(package / 'manifest.json')
    plan = read(build / 'derived/manifest.json')['plan']
    return literal_gate.check_release(package, manifest, {k: str(p) for k, p in bases.items()},
        [f'{k}={p}' for k, p in sources.items()], {'everything': str(build)}, plans={'everything': plan})


def validate_manifest(manifest):
    if (manifest.get('format') != 3 or manifest.get('default') != 'everything' or
            set(manifest.get('variants', {})) != {'everything'} or set(manifest.get('bases', {})) != BASES or
            set(manifest['variants']['everything']['outputs']) != BASES):
        raise RuntimeError('reuse requires the complete seven-base everything package')


def prepare(a, r, info):
    """Seal a final proof at its original clean commit, before tagging."""
    import release
    package, images, build, engine = (p.expanduser().resolve() for p in
        (a.reuse_package, a.reuse_outputs, a.reuse_build, a.reuse_engine))
    manifest = read(package / 'manifest.json')
    validate_manifest(manifest)
    # A dirty make-release or unrelated source tree cannot be certified afterwards.
    require_equal(release.git('rev-parse', manifest['commit'] + '^{tree}'),
                  release.git('rev-parse', 'HEAD^{tree}'), 'package source tree')
    bases = {k: Path(p).resolve() for k, p in read(a.reuse_bases).items()}
    sources = {k: Path(p).resolve() for k, p in read(a.reuse_sources).items()}
    require_equal(set(bases), BASES, 'registered bases')
    from discs import DISCS, DW1_RELEASES, SOURCE_DISCS
    expected = {'us': DISCS[0]['sha1'], **{d['id'][4:]: d['sha1'] for d in DW1_RELEASES if d['supported']},
                **{d['id']: d['sha1'] for d in SOURCE_DISCS}}
    for key, path in {**bases, **sources}.items():
        require_equal(release.sha1(path), expected[key], 'registered input ' + key)
        if key in bases:
            require_equal(manifest['bases'][key]['sha1'], expected[key], key + ' manifest input')
            require_equal(manifest['bases'][key]['size'], path.stat().st_size, key + ' manifest input size')
    require_equal(set(sources), set(manifest.get('source_discs', [])), 'source disc set')
    if r.out.exists():
        raise RuntimeError('handoff output must be a new directory')
    # Dry run never claims that supplied artifacts have been certified.
    if r.dry:
        print('Would verify publication, engine/package identity, all seven image/file sums and seal source tree')
        return
    r.out.mkdir(parents=True)
    r.created = True
    if read(package / 'literal-gate.json').get('passed') is not True:
        raise RuntimeError('reuse requires an already passed final publication gate')
    engine_package(engine, package)
    # Never overwrite the proof owner's artifacts, including its gate report.
    snapshot = r.out / 'package'
    shutil.copytree(package, snapshot, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    package = snapshot
    with r.step('Recheck final proof publication and engine binding'):
        publication(package, build, bases, sources)
        engine_package(engine, package)
    with r.step('Seal seven verified images and current source tree'):
        offset = version_offset(build / 'exe/SLUS_010.32.elf.map')
        outputs, sums = {}, {}
        for key, pin in manifest['variants']['everything']['outputs'].items():
            path = images / f'everything-{key}.bin'
            require_equal(path.stat().st_size, pin['size'], key + ' image size')
            require_equal(release.sha1(path), pin['sha1'], key + ' image SHA-1')
            image = iw.Image(str(path))
            try:
                stamp(image.read(EXE), offset, manifest['version'], manifest['version'])
                for hole in manifest['variants']['everything']['holes']:
                    require_equal(digest(image.read(hole['file'])), hole.get('sha1_by_base', {}).get(key, hole['sha1']), key + ' hole')
            finally:
                image.f.close()
            outputs[key] = dict(path=str(path), **pin)
            sums[key] = file_sums(path)
        audit = {str(p.relative_to(build)): release.sha1(p) for p in audit_build_files(build)}
        require_equal(release.identity(a.tag), info, 'checkout identity before sealing')
        write(r.out / 'reuse.json', dict(schema=1, tree=release.git('rev-parse', 'HEAD^{tree}'), info=info,
            package=str(package), package_files=inventory(package), engine=str(engine), engine_files=inventory(engine),
            build=str(build), audit_files=audit, outputs=outputs, file_sums=sums, offset=offset,
            inputs={k: dict(path=str(p), sha1=release.sha1(p)) for k, p in {**bases, **sources}.items()},
            bases=list(bases), sources=list(sources)))


def reuse(a, r, info):
    import release
    seal = read(a.reuse_from / 'reuse.json')
    if seal.get('schema') != 1:
        raise RuntimeError('unsupported reuse handoff')
    require_equal(release.git('rev-parse', 'HEAD^{tree}'), seal['tree'], 'tracked source tree')
    if a.skip_browser or a.record_save or a.save_check_emu:
        raise RuntimeError('reuse requires browser gate; save recording/emulator options need the full pipeline')
    out = r.out
    if out.exists():
        raise RuntimeError('output must be a new directory')
    package, engine, build = (Path(seal[k]) for k in ('package', 'engine', 'build'))
    with r.step('Validate sealed package, engine, audit inputs and seven outputs'):
        require_equal(inventory(package), seal['package_files'], 'package file sums')
        require_equal(inventory(engine), seal['engine_files'], 'engine file sums')
        require_equal({str(p.relative_to(build)): release.sha1(p) for p in audit_build_files(build)}, seal['audit_files'], 'audit files')
        for key, value in seal['inputs'].items():
            require_equal(release.sha1(value['path']), value['sha1'], key + ' input')
        for key, value in seal['outputs'].items():
            require_equal(Path(value['path']).stat().st_size, value['size'], key + ' image size')
            require_equal(release.sha1(value['path']), value['sha1'], key + ' image')
            require_equal(file_sums(value['path']), seal['file_sums'][key], key + ' disc-file sums')
        engine_package(engine, package)
    if r.dry:
        print('Would restamp seven images, recompute executable deltas, publication gate, Python 3.10 cached-hole USA apply, repack engine, browser checksum and archive')
        return
    out.mkdir(parents=True)
    r.created = True
    dest = out / 'package'
    shutil.copytree(package, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    audit = out / 'audit-build'
    for rel in seal['audit_files']:
        target = audit / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(build / rel, target)
    bases = {k: Path(seal['inputs'][k]['path']) for k in seal['bases']}
    sources = {k: Path(seal['inputs'][k]['path']) for k in seal['sources']}
    manifest = read(dest / 'manifest.json')
    validate_manifest(manifest)
    variant = manifest['variants']['everything']
    old = manifest['version']
    with r.step('Restamp fixed version buffer and recompute seven executable deltas'):
        payload = dw.read_payload3(dw.read_patch_file(str(dest), variant))
        originals = {k: iw.Image(str(p)) for k, p in bases.items()}
        try:
            restamp_payload(payload, originals, seal['offset'], old, info['version'])
        finally:
            for image in originals.values():
                image.f.close()
        save_payload(dest / variant['patch'], payload)
        variant.update(patch_size=(dest / variant['patch']).stat().st_size,
                       patch_sha1=release.sha1(dest / variant['patch']))
        images = out / 'outputs'
        images.mkdir()
        proof = {}
        for key, pin in seal['outputs'].items():
            target = images / f'everything-{key}.bin'
            proof[key] = restamp_image(pin['path'], target, seal['offset'], old, info['version'])
            require_equal(proof[key]['before'], seal['file_sums'][key], key + ' original file sums')
            variant['outputs'][key] = dict(sha1=release.sha1(target), size=target.stat().st_size)
            r.sums['output-' + key] = variant['outputs'][key]['sha1']
        manifest.update(version=info['version'], date=info['date'], commit=info['commit'])
        write(dest / 'manifest.json', manifest)
        write(out / 'restamp-proof.json', proof)
        # Keep the original construction audit explicitly historical rather than
        # silently presenting its old output pins as the release's current ones.
        audit_text = dest / 'audit.txt'
        if audit_text.exists():
            audit_text.write_text('Historical construction audit before version restamping.\n'
                'Current metadata/output pins: manifest.json; restamp provenance: restamp.json.\n\n'
                + audit_text.read_text())
        write(dest / 'restamp.json', dict(tree=seal['tree'], from_version=old,
            to_version=info['version'], version_offset=seal['offset'], version_size=32,
            original_manifest_sha1=seal['package_files']['manifest.json'],
            original_outputs={k: v['sha1'] for k, v in seal['outputs'].items()},
            outputs=variant['outputs']))
    with r.step('Publication gate on restamped package'):
        publication(dest, audit, bases, sources)
    with r.step('Verify all seven restamped package outputs without derivation'):
        verify_outputs(dest, images, bases, sources)
    with r.step('Standalone Python 3.10 USA apply with verified retained holes'):
        # This checks the shipped writer/deltas in isolation. Derive bytes are unchanged
        # and checked individually; the browser below independently reruns derivation.
        runner = out / 'cached_apply.py'
        shutil.copyfile(ROOT / 'tools/release_cached_apply.py', runner)
        cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', str(a.jobs),
               '--user', f'{os.getuid()}:{os.getgid()}']
        for path in sorted({out, *[p.parent for p in (*bases.values(), *sources.values())]}, key=str):
            cmd += ['-v', f'{path}:{path}' + ('' if path == out else ':ro')]
        cmd += ['-w', out, 'python:3.10-slim', 'python', '-B', '-I', '-S', runner,
                dest, bases['us'], images / 'everything-us.bin', out / 'standalone.bin']
        for key, path in sources.items():
            cmd += [f'{key}={path}']
        r.cmd(cmd)
        require_equal(release.sha1(out / 'standalone.bin'), variant['outputs']['us']['sha1'], 'Python 3.10 USA apply')
        (out / 'standalone.bin').unlink()
    with r.step('Repack verified engine graph with current manifest and deltas'):
        repack_engine(engine, out / 'engine', dest)
    with r.step('USA browser suite on restamped candidate'):
        release.browser(r, out, out / 'engine', bases, sources, dict(os.environ))
    with r.step('Package archive and file sums'):
        archive = out / ('horizon-' + info['version'] + '.tar.gz')
        release.pack_release(dest, archive)
        write(out / 'package-sums.json', inventory(dest))
        r.sums[str(archive)] = release.sha1(archive)
    require_equal(release.identity(a.tag), info, 'checkout identity at completion')
    if a.deploy:
        r.cmd(['web/deploy.sh'], dict(os.environ, RELEASE=str(dest), ENGINE=str(out / 'engine')))
    if a.publish:
        r.cmd(['git', 'push', a.remote, f'refs/tags/{a.tag}:refs/tags/{a.tag}'])
        r.cmd(['gh', 'release', 'create', a.tag, archive, '--verify-tag',
               '--title', 'Digimon World Horizon ' + info['version'], '--notes-file', a.notes_file])
