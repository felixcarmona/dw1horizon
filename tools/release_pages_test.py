#!/usr/bin/env python3
"""Publication boundary regressions. All payload bytes here are synthetic."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

import release_pages as pages


def fixture(info):
    manifest = dict(format=3, **{k: info[k] for k in ('version', 'date', 'commit')},
                    default='everything', variants={'everything': {
                        'patch': 'everything.dwp', 'local': {'builder': 'derive'},
                        'outputs': {'us': {'sha1': '0' * 40}}}})
    data = json.dumps(manifest).encode()
    package = {'manifest.json': data, 'everything.dwp': b'synthetic patch',
               **{n: b'synthetic fixture only' for n in ('dwpatch.py', 'isowriter.py', 'audit.txt', 'README.md')}}
    recipe = 'tools/derive/recipes/everything.json'
    package['bundle/' + recipe] = (pages.ROOT / recipe).read_bytes()
    plan = dict(release=dict(version=info['version'], commit=info['commit'],
                            outputs=manifest['variants']['everything']['outputs']),
                packs=[dict(name='code.pack', size=len(data), sha1=hashlib.sha1(data).hexdigest())],
                files=[['.release/manifest.json', 0, 0, len(data), len(data), 0]],
                pyodide={'files': []})
    text = json.dumps(plan).encode()
    version = hashlib.sha1(text + plan['packs'][0]['sha1'].encode()).hexdigest()[:12]
    engine = {version + '/plan.json': text, version + '/packs/code.pack': data,
              'current.json': json.dumps(dict(version=version, release_version=info['version'],
                                             release_date=info['date'], commit=info['commit'])).encode()}
    return package, engine


class PublicationTests(unittest.TestCase):
    info = dict(version='1.2.3', date='2026-10-29', commit='a' * 40)

    def test_identity_and_pack_corruption(self):
        package, engine = fixture(self.info)
        pages.validate(package, engine, self.info)
        for key in ('version', 'date', 'commit'):
            with self.assertRaisesRegex(ValueError, key):
                pages.validate(package, engine, dict(self.info, **{key: 'wrong'}))
        name = next(n for n in engine if n.endswith('.pack'))
        engine[name] += b'corrupt'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            pages.validate(package, engine, self.info)

    def test_package_writes_the_full_commit(self):
        sys.path.insert(0, str(pages.ROOT / 'tools/patcher'))
        import dwpatch
        self.assertEqual(dwpatch.git_commit().split('+')[0], pages.release.git('rev-parse', 'HEAD'))

    def test_local_paths_are_refused(self):
        for path in (b'/var/tmp/build/x.map', b'/Users/someone/game.bin',
                     b'C:\\Users\\someone\\game.bin'):
            package, engine = fixture(self.info)
            package['audit.txt'] += path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'local path in package'):
                pages.validate(package, engine, self.info)

    def test_embedded_manifest_is_exact_package(self):
        package, engine = fixture(self.info)
        package['manifest.json'] += b' '
        with self.assertRaisesRegex(ValueError, 'embedded manifest'):
            pages.validate(package, engine, self.info)

    def test_unlisted_engine_data_is_refused(self):
        package, engine = fixture(self.info)
        version = json.loads(engine['current.json'])['version']
        engine[version + '/private.dat'] = b'not allowed'
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            pages.validate(package, engine, self.info)

    def test_archives_cannot_escape_or_smuggle_discs_and_links(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'payload.tar.gz'
            for name, kind in [('../outside', tarfile.REGTYPE), ('/outside', tarfile.REGTYPE),
                               ('a/../outside', tarfile.REGTYPE), ('game.BIN', tarfile.REGTYPE),
                               ('extracted/model.dat', tarfile.REGTYPE), ('link', tarfile.SYMTYPE),
                               ('hardlink', tarfile.LNKTYPE), ('device', tarfile.CHRTYPE)]:
                with self.subTest(name=name, kind=kind):
                    with tarfile.open(target, 'w:gz') as archive:
                        member = tarfile.TarInfo(name)
                        member.type = kind
                        archive.addfile(member)
                    with self.assertRaises(ValueError):
                        pages.read_archive(target)

    def test_archive_roundtrip_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'payload.tar.gz'
            pages.write_archive(target, {'bundle/code.py': b'authored'})
            self.assertEqual(pages.read_archive(target), {'bundle/code.py': b'authored'})
            with tarfile.open(target, 'w:gz') as archive:
                for _ in range(2):
                    archive.addfile(tarfile.TarInfo('duplicate'))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                pages.read_archive(target)


if __name__ == '__main__':
    unittest.main()
