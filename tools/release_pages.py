#!/usr/bin/env python3
"""Disc-free Pages assembly; prepared engines/packages still require the local release gates.

See docs/release/releasing.md. Only the standard library is used. Input archives
are data: no bundled Python or shell scripts are executed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

import release

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'horizon-package.tar.gz'
ENGINE = 'horizon-engine.tar.gz'
LIMIT = 900 * 1024 * 1024
RAW = {'.bin', '.cue', '.iso', '.img', '.chd', '.ecm', '.pbp', '.str', '.xa', '.vab'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed(name):
    p = PurePosixPath(name)
    require(name not in ('', '.') and str(p) == name and not p.is_absolute()
            and '..' not in p.parts and '\\' not in name,
            f'unsafe path: {name}')
    require(p.suffix.lower() not in RAW, f'disc/game file refused: {name}')
    require(not set(p.parts) & {'extracted', 'source-games', '__pycache__', '.git'},
            f'private/scratch path refused: {name}')


def files(folder):
    result = {}
    for p in sorted(folder.rglob('*')):
        require(not p.is_symlink(), f'links are not publishable: {p}')
        if '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        if p.is_file():
            name = p.relative_to(folder).as_posix()
            allowed(name)
            result[name] = p.read_bytes()
    require(sum(map(len, result.values())) < LIMIT, 'payload exceeds Pages budget')
    return result


def read_archive(path):
    result, total = {}, 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            allowed(member.name)
            if member.isdir():
                continue
            require(member.isfile(), f'archive links/special files refused: {member.name}')
            require(member.name not in result, f'duplicate member: {member.name}')
            total += member.size
            require(total < LIMIT, 'archive exceeds size budget')
            result[member.name] = archive.extractfile(member).read()
    return result


def write_archive(path, entries):
    with tarfile.open(path, 'w:gz') as archive:
        for name, data in sorted(entries.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))


def load(entries, name):
    return json.loads(entries[name])


def validate(package, engine, info):
    m = load(package, 'manifest.json')
    require(m.get('format') == 3, 'expected format 3 patch package')
    for key in ('version', 'date', 'commit'):
        require(m.get(key) == info[key], f'package {key} differs from tag')
    for name in ('dwpatch.py', 'isowriter.py', 'audit.txt', 'README.md'):
        require(name in package, f'package missing {name}')
    variant = m['variants'][m['default']]
    require(variant['patch'] in package, 'package missing patch')
    require(variant['local'].get('builder') == 'derive', 'expected derive builder')
    recipe = 'tools/derive/recipes/everything.json'
    require(package.get('bundle/' + recipe) == (ROOT / recipe).read_bytes(),
            'package recipe differs from checkout; page languages would be incorrect')
    cur = load(engine, 'current.json')
    version = cur['version']
    require(re.fullmatch('[0-9a-f]{12}', version), 'invalid engine hash')
    require(cur.get('release_version') == info['version'] and
            cur.get('release_date') == info['date'] and cur.get('commit') == info['commit'],
            'engine identity differs from tag')
    require(all(n == 'current.json' or n.startswith(version + '/') for n in engine),
            'engine must contain only current.json and the latest version folder')
    plan_bytes = engine[version + '/plan.json']
    plan = json.loads(plan_bytes)
    require(plan['release']['commit'] == info['commit'] and
            plan['release']['version'] == info['version'], 'plan identity differs from tag')
    require(plan['release']['outputs'] == variant['outputs'], 'plan output pins differ from package')
    hash_input = plan_bytes + b''.join(p['sha1'].encode() for p in plan['packs'])
    require(hashlib.sha1(hash_input).hexdigest()[:12] == version, 'engine hash mismatch')
    expected = {'current.json', version + '/plan.json'}
    expected.update(version + '/packs/' + p['name'] for p in plan['packs'])
    expected.update(version + '/pyodide/' + name for name, _ in plan['pyodide']['files'])
    require(set(engine) == expected, 'unexpected or missing engine files')
    for pack in plan['packs']:
        data = engine[version + '/packs/' + pack['name']]
        require(len(data) == pack['size'] and hashlib.sha1(data).hexdigest() == pack['sha1'],
                'engine pack checksum mismatch')
    for name, size in plan['pyodide']['files']:
        require(len(engine[version + '/pyodide/' + name]) == size, 'runtime size mismatch')
    for row in plan['files']:
        allowed(row[0])
    # The embedded manifest must be the exact package's manifest, not another build.
    import zlib
    embedded = next(row for row in plan['files'] if row[0] == '.release/manifest.json')
    _, pack, offset, stored, size, method = embedded
    data = engine[version + '/packs/' + plan['packs'][pack]['name']][offset:offset + stored]
    require(method in (0, 8), 'unsupported pack compression')
    require(size == len(package['manifest.json']), 'embedded manifest size differs')
    if method == 8:
        data = zlib.decompressobj(-15).decompress(data, size + 1)
    require(len(data) == size and data == package['manifest.json'], 'embedded manifest differs')
    return cur


def page(out):
    require(not out.exists(), f'output must be a new directory: {out}')
    # Copy tracked assets only: never developer clips, caches, tests, or engine tooling.
    names = release.git('ls-files', 'web').splitlines()
    entries = {}
    roots = {'js', 'i18n', 'data', 'content', 'media'}
    top = {'index.html', 'style.css', 'favicon.svg', 'engine-sw.js', 'CNAME'}
    for name in names:
        rel = Path(name).relative_to('web')
        if (len(rel.parts) == 1 and rel.name in top) or rel.parts[0] in roots:
            allowed(rel.as_posix())
            require(not (ROOT / name).is_symlink(), f'linked page asset: {name}')
            entries[rel.as_posix()] = (ROOT / name).read_bytes()
    # Showcase recordings are intentionally absent from the public source.
    # Render those cards as text rather than requesting private/missing media.
    features_key = (Path('content') / 'features.json').as_posix()
    features = json.loads(entries[features_key])
    def available(media):
        for field in ('src', 'poster', 'webm'):
            values = media.get(field, {})
            values = values.values() if isinstance(values, dict) else [values]
            if any(value not in entries for value in values):
                return False
        return True
    for feature in features['features']:
        feature['media'] = [m for m in feature['media'] if available(m)]
    if not any(f['media'] for f in features['features']):
        features.pop('note', None)
    entries[features_key] = (json.dumps(features, ensure_ascii=False) + '\n').encode()
    out.mkdir(parents=True)
    for name, data in entries.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    subprocess.run(['python3', str(ROOT / 'tools/discs.py'), 'web-json',
                    str(out / 'data/discs.json'), '--recipe',
                    str(ROOT / 'tools/derive/recipes/everything.json')], check=True)
    for name in ('LICENSE', 'THIRD-PARTY.md'):
        (out / name).write_bytes((ROOT / name).read_bytes())
    shutil.copytree(ROOT / 'tools/font/japanese-license',
                    out / 'licenses/japanese-font', dirs_exist_ok=True)
    (out / 'licenses').mkdir(exist_ok=True)
    (out / 'licenses/raster.txt').write_bytes((ROOT / 'tools/image-license.txt').read_bytes())
    (out / '.nojekyll').write_text('')


def build(a):
    info = release.identity(a.tag)
    package = read_archive(a.inputs / PACKAGE)
    engine = read_archive(a.inputs / ENGINE)
    checks = json.loads((a.inputs / 'horizon-checksums.json').read_text())
    require(checks == {kind: {n: digest(d) for n, d in entries.items()}
                       for kind, entries in [('package', package), ('engine', engine)]},
            'prepared asset inventory mismatch')
    cur = validate(package, engine, info)
    page(a.out)
    for name, data in engine.items():
        p = a.out / 'engine' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    # Add tag as metadata without mutating the immutable engine folder or package.
    cur['release_tag'] = a.tag
    (a.out / 'engine/current.json').write_text(json.dumps(cur) + '\n')
    total = sum(p.stat().st_size for p in a.out.rglob('*') if p.is_file())
    require(total < LIMIT, 'site exceeds Pages budget')
    require(all(p.stat().st_size < 100 * 1024 * 1024 for p in a.out.rglob('*') if p.is_file()),
            'site file exceeds 100 MiB')
    metadata = dict(info, tag=a.tag)
    (a.inputs / 'release.json').write_text(json.dumps(metadata) + '\n')
    (a.inputs / 'release-notes.md').write_text(
        f"Digimon World: Horizon {info['version']} ({info['date']}, UTC).\n\n"
        'Apply the attached package to your own discs; see its README.\n\n'
        f"Source commit: {info['commit']}.\n")
    print(json.dumps(metadata))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='archive locally verified artifacts; no disc reads')
    prepare.add_argument('tag')
    prepare.add_argument('--package', type=Path, required=True)
    prepare.add_argument('--engine', type=Path, required=True)
    prepare.add_argument('--out', type=Path, required=True)
    site = sub.add_parser('build', help='validate prepared assets and assemble Pages')
    site.add_argument('tag')
    site.add_argument('--inputs', type=Path, required=True)
    site.add_argument('--out', type=Path, required=True)
    preview = sub.add_parser('page', help='page-only preview, no playable engine; never deployed by CI')
    preview.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    if a.command == 'page':
        page(a.out)
    elif a.command == 'build':
        build(a)
    else:
        info = release.identity(a.tag)
        package, engine = files(a.package), files(a.engine)
        validate(package, engine, info)
        require(not a.out.exists(), 'prepare output must be a new directory')
        a.out.mkdir(parents=True)
        write_archive(a.out / PACKAGE, package)
        write_archive(a.out / ENGINE, engine)
        (a.out / 'horizon-checksums.json').write_text(json.dumps({
            kind: {n: digest(d) for n, d in entries.items()}
            for kind, entries in [('package', package), ('engine', engine)]}, indent=2) + '\n')


if __name__ == '__main__':
    main()
