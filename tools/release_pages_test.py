#!/usr/bin/env python3
"""Publication boundary regressions. All payload bytes here are synthetic."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import release_pages as pages
import discs


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


class DiscMetadataTests(unittest.TestCase):
    def fixture(self, root):
        def model(sid, folder):
            return dict(id=sid, name='Renamed' + str(sid),
                        mmd={'sources': [{'path': folder + '/Shared.MMD'},
                                         {'path': 'extracted/CHDAT/MMD0/NATIVE.MMD'}]},
                        tim={'sources': [{'path': folder + '/Shared.TIM'}]})
        recipes = [dict(out=folder, entry=dict(name='Shared', game=game))
                   for folder, game in [('build/old', 'dcb'), ('build/new', 'dw3')]]
        entries = {'content/modeldelta/models.json': {'models': [model(1, 'build/new'), model(2, 'build/old')]},
                   'content/modeldelta/import-batches.json': {'recipes': recipes},
                   'content/models/dcb-import/veemon-dw2.json': {'dw2': {}},
                   'content/models/dcb-import/puppetmon.json': {'dcb': {}},
                   'content/models/dcb-import/kimeramon-dw2.json': {'dw2': {}},
                   'content/models/mega/wargreymon-dcb.json': {'dcb': {}}}
        for name, value in entries.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        return entries

    def test_shared_filename_uses_current_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            self.assertEqual(discs.species_counts(root), dict(dcb=1, dw2=0, dw2003=1))

    def test_missing_and_conflicting_import_sources_still_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            entries = self.fixture(root)
            path = root / 'content/modeldelta/import-batches.json'
            recipes = entries['content/modeldelta/import-batches.json']['recipes']
            for changed in [recipes[:1], recipes + [dict(out='build/new', entry=dict(name='Shared', game='dcb'))]]:
                with self.subTest(recipes=changed):
                    path.write_text(json.dumps({'recipes': changed}))
                    with self.assertRaisesRegex(ValueError, 'species 1 Renamed1: its game is not clear'):
                        discs.species_counts(root)

    def test_current_release_catalog_can_generate_disc_metadata(self):
        counts = discs.species_counts()
        models = json.loads((pages.ROOT / 'content/modeldelta/models.json').read_text())['models']
        self.assertEqual(sum(counts.values()), len(models))
        self.assertEqual(set(counts), {disc['id'] for disc in discs.SOURCE_DISCS})


class PublicationTests(unittest.TestCase):
    info = dict(version='1.2.3', date='2026-10-29', commit='a' * 40)

    def test_changelog_notes(self):
        entry = dict(new=['A new feature'], changed=[], fixed=['A fix'], upgrade='Previous saves work; discs unchanged.')
        notes = pages.release_notes(self.info, entry)
        self.assertEqual(notes, "Digimon World: Horizon 1.2.3 (2026-10-29, UTC).\n\n"
                         "## New\n\n- A new feature\n\n## Fixed\n\n- A fix\n\n"
                         "Previous saves work; discs unchanged.\n\n"
                         "Apply the attached package to your own discs; see its README.\n\n"
                         f"Source commit: {self.info['commit']}.\n")
        self.assertNotIn('Upgrade', pages.release_notes(self.info, dict(new=[], changed=[], fixed=[])))

    def test_changelog_lookup_and_missing_release_gates(self):
        with tempfile.TemporaryDirectory() as td, patch.object(pages, 'ROOT', Path(td)):
            path = Path(td) / 'web/content/changelog.json'
            with self.assertRaisesRegex(ValueError, 'missing changelog'):
                pages.changelog_entry('1.2.3')
            path.parent.mkdir(parents=True)
            entry = dict(new=['First release'], changed=[], fixed=[])
            path.write_text(json.dumps(dict(versions=[dict(version='1.2.3', en=entry)])))
            self.assertEqual(pages.changelog_entry('1.2.3'), entry)
            with patch.object(pages.release, 'identity', return_value=dict(self.info, version='9.9.9')):
                with self.assertRaisesRegex(ValueError, 'missing English changelog entry for version 9.9.9'):
                    pages.build(SimpleNamespace(tag='v9.9.9'))
                with patch.object(sys, 'argv', ['release_pages.py', 'prepare', 'v9.9.9', '--package', 'unused', '--engine', 'unused', '--out', 'unused']):
                    with self.assertRaisesRegex(ValueError, 'missing English changelog entry for version 9.9.9'):
                        pages.main()

    def test_build_writes_changelog_notes_and_release_tag(self):
        package, engine = fixture(self.info)
        entry = dict(new=['A feature'], changed=['A change'], fixed=[])
        with tempfile.TemporaryDirectory() as td:
            inputs = Path(td) / 'inputs'
            inputs.mkdir()
            pages.write_archive(inputs / pages.PACKAGE, package)
            pages.write_archive(inputs / pages.ENGINE, engine)
            (inputs / 'horizon-checksums.json').write_text(json.dumps({
                kind: {name: pages.digest(data) for name, data in entries.items()}
                for kind, entries in [('package', package), ('engine', engine)]}))
            out = Path(td) / 'site'
            with patch.object(pages.release, 'identity', return_value=self.info), \
                    patch.object(pages, 'changelog_entry', return_value=entry) as lookup, \
                    patch.object(pages, 'page', side_effect=lambda dest: dest.mkdir()):
                pages.build(SimpleNamespace(tag='v1.2.3', inputs=inputs, out=out))
            lookup.assert_called_once_with('1.2.3')
            self.assertEqual((inputs / 'release-notes.md').read_text(), pages.release_notes(self.info, entry))
            cur = json.loads((out / 'engine/current.json').read_text())
            self.assertEqual(cur['release_tag'], 'v1.2.3')
            self.assertNotIn('desktop', cur)

    def desktop_inputs(self, folder, tag='v1.2.3', with_linux=False, **changes):
        """horizon-desktop.json and the two zips, as desktop.yml attaches them (synthetic bytes)."""
        folder.mkdir(parents=True, exist_ok=True)
        info = {'tag': tag, 'run': 'https://github.com/owner/repo/actions/runs/123'}
        for os_name, name in {**pages.DESKTOP, **(pages.DESKTOP_OPTIONAL if with_linux else {})}.items():
            data = f'synthetic {os_name} app'.encode()
            (folder / name).write_bytes(data)
            info[os_name] = dict(name=name, size=len(data), sha256=pages.digest(data),
                                 **{'windows': {'signed': False}, 'macos': {'notarized': True}}.get(os_name, {}))
        info.update(changes)
        (folder / 'horizon-desktop.json').write_text(json.dumps(info))
        return info

    def test_desktop_apps(self):
        package = {'dwpatch.py': b'VERSION = 1\nGUI_API = 1\n'}
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'desktop'
            # no apps on the release (v0.0.4 and earlier, or desktop.yml not done yet): nothing offered
            self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.3'))
            info = self.desktop_inputs(folder)
            apps = pages.desktop_apps(folder, package, 'v1.2.3')
            self.assertEqual(apps['windows'], info['windows'])
            self.assertEqual(apps['macos'], info['macos'])
            self.assertEqual(apps['run'], info['run'])
            self.assertNotIn('linux', apps)   # (the release has none: Windows and macOS alone)
            # the Linux tarball, when it is listed and matches
            info = self.desktop_inputs(folder, with_linux=True)
            apps = pages.desktop_apps(folder, package, 'v1.2.3')
            self.assertEqual(apps['linux'], info['linux'])
            self.assertEqual(apps['windows'], info['windows'])
            # a bad Linux entry drops only Linux, with a warning
            linux = folder / pages.DESKTOP_OPTIONAL['linux']
            bad_name = dict(info['linux'], name='other.tar.gz')
            for what, change in (('another build', lambda: linux.write_bytes(b'another build')),
                                 ('missing', linux.unlink),
                                 ('wrong name', lambda: self.desktop_inputs(folder, with_linux=True, **{'linux': bad_name}))):
                with self.subTest(linux=what), contextlib.redirect_stdout(io.StringIO()) as out:
                    info = self.desktop_inputs(folder, with_linux=True)
                    change()
                    apps = pages.desktop_apps(folder, package, 'v1.2.3')
                    self.assertEqual(sorted(apps), ['macos', 'run', 'windows'])
                    self.assertIn('::warning::', out.getvalue())
            self.desktop_inputs(folder)
            # a package whose dwpatch predates the app's interface: the app would refuse it
            self.assertIsNone(pages.desktop_apps(folder, {'dwpatch.py': b'VERSION = 1\n'}, 'v1.2.3'))
            # another tag's description
            self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.4'))
            # a zip missing or different from the description
            (folder / pages.DESKTOP['macos']).write_bytes(b'another build')
            self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.3'))
            (folder / pages.DESKTOP['macos']).unlink()
            self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.3'))
            for changes in ({'windows': None}, {'run': 'https://example.com/x'}, {'run': 5},
                            {'macos': dict(info['macos'], name='other.zip')},
                            {'macos': dict(info['macos'], notarized='yes')}):
                with self.subTest(changes=changes):
                    self.desktop_inputs(folder, **changes)
                    self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.3'))
            (folder / 'horizon-desktop.json').write_text('not json')
            self.assertIsNone(pages.desktop_apps(folder, package, 'v1.2.3'))

    def test_build_records_the_desktop_apps(self):
        package, engine = fixture(self.info)
        package['dwpatch.py'] = b'GUI_API = 1\n'
        with tempfile.TemporaryDirectory() as td:
            inputs = Path(td) / 'inputs'
            inputs.mkdir()
            pages.write_archive(inputs / pages.PACKAGE, package)
            pages.write_archive(inputs / pages.ENGINE, engine)
            (inputs / 'horizon-checksums.json').write_text(json.dumps({
                kind: {name: pages.digest(data) for name, data in entries.items()}
                for kind, entries in [('package', package), ('engine', engine)]}))
            info = self.desktop_inputs(inputs / 'desktop')
            out = Path(td) / 'site'
            with patch.object(pages.release, 'identity', return_value=self.info), \
                    patch.object(pages, 'changelog_entry', return_value=dict(new=[], changed=[], fixed=[])), \
                    patch.object(pages, 'page', side_effect=lambda dest: dest.mkdir()):
                pages.build(SimpleNamespace(tag='v1.2.3', inputs=inputs, out=out))
            cur = json.loads((out / 'engine/current.json').read_text())
            self.assertEqual(cur['desktop']['windows']['sha256'], info['windows']['sha256'])
            self.assertTrue(cur['desktop']['macos']['notarized'])
            # the zips themselves are not part of the site
            self.assertFalse(any(p.suffix == '.zip' for p in out.rglob('*')))

    def player_inputs(self, folder, kinds=tuple(pages.PLAYERS), digests=True, **changes):
        """The installer templates and assets.json, as release.yml downloads them (synthetic bytes)."""
        folder.mkdir(parents=True, exist_ok=True)
        assets = []
        for kind in kinds:
            name = pages.PLAYERS[kind]
            data = pages.PLAYER_MAGIC[kind] + f'synthetic {kind} template'.encode()
            (folder / name).write_bytes(data)
            assets.append(dict(name=name, size=len(data), digest='sha256:' + pages.digest(data) if digests else None))
        assets.append(dict(name='horizon-package.tar.gz', size=1, digest=None))
        for a in assets:
            a.update(changes.get(a['name'], {}))
        (folder / 'assets.json').write_text(json.dumps(assets))

    def test_players(self):
        with tempfile.TemporaryDirectory() as td:
            folder, out = Path(td) / 'players', Path(td) / 'site'
            # none on the release (up to v0.0.10): nothing offered, nothing written
            self.assertIsNone(pages.players(folder, out, 'v1.2.3'))
            self.player_inputs(folder)
            got = pages.players(folder, out, 'v1.2.3')
            self.assertEqual(sorted(got), sorted(pages.PLAYERS))
            for kind, name in pages.PLAYERS.items():
                data = (folder / name).read_bytes()
                self.assertEqual(got[kind]['url'], f'players/v1.2.3/{name}')
                self.assertEqual((out / got[kind]['url']).read_bytes(), data)
                self.assertEqual((got[kind]['size'], got[kind]['sha256']), (len(data), pages.digest(data)))
            # what the browser needs beside them: the shared APK key, the .run's header (with its SKIP), the icon
            self.assertEqual((out / got['apk']['key']).read_bytes(),
                             (pages.ROOT / 'tools/patcher/android-key.json').read_bytes())
            header = (out / got['linux']['header']).read_text()
            self.assertIn(f'SKIP={len(header.encode()):<10d}', header)
            self.assertTrue((out / got['linux']['icon']).read_bytes().startswith(b'\x89PNG'))
            # GitHub gives no digest: the size decides
            out2 = Path(td) / 'site2'
            self.player_inputs(folder, digests=False)
            self.assertEqual(sorted(pages.players(folder, out2, 'v1.2.3')), sorted(pages.PLAYERS))

    def test_players_bad_ones_are_left_out(self):
        apk, linux = pages.PLAYERS['apk'], pages.PLAYERS['linux']
        cases = {'missing': (lambda f: (f / linux).unlink(), {}),
                 'size': (None, {linux: {'size': 1}}),
                 'digest': (None, {linux: {'digest': 'sha256:' + '0' * 64}}),
                 'not listed': (None, {linux: {'name': 'other'}}),
                 'not a tarball': (lambda f: (f / linux).write_bytes(b'MZ'), {linux: {'size': 2, 'digest': None}})}
        for what, (change, assets) in cases.items():
            with self.subTest(what), tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stdout(io.StringIO()) as log:
                folder, out = Path(td) / 'players', Path(td) / 'site'
                self.player_inputs(folder, **assets)
                if change:
                    change(folder)
                got = pages.players(folder, out, 'v1.2.3')
                self.assertEqual(sorted(got), ['apk', 'mac', 'setup'])
                self.assertFalse((out / 'players/v1.2.3/linux-run-header.sh').exists())
                self.assertFalse((out / 'players/v1.2.3' / linux).exists())
                if what != 'missing':
                    self.assertIn('::warning::', log.getvalue())
        # only Linux: no signing key on the site
        with tempfile.TemporaryDirectory() as td:
            folder, out = Path(td) / 'players', Path(td) / 'site'
            self.player_inputs(folder, kinds=('linux',))
            self.assertEqual(sorted(pages.players(folder, out, 'v1.2.3')), ['linux'])
            self.assertFalse((out / 'players/v1.2.3/android-key.json').exists())
            self.assertFalse((out / 'players/v1.2.3' / apk).exists())
            # no list of the assets: nothing is offered
            (folder / 'assets.json').unlink()
            with contextlib.redirect_stdout(io.StringIO()) as log:
                self.assertIsNone(pages.players(folder, Path(td) / 'site2', 'v1.2.3'))
            self.assertIn('::warning::', log.getvalue())

    def test_build_records_the_players(self):
        package, engine = fixture(self.info)
        with tempfile.TemporaryDirectory() as td:
            inputs = Path(td) / 'inputs'
            inputs.mkdir()
            pages.write_archive(inputs / pages.PACKAGE, package)
            pages.write_archive(inputs / pages.ENGINE, engine)
            (inputs / 'horizon-checksums.json').write_text(json.dumps({
                kind: {name: pages.digest(data) for name, data in entries.items()}
                for kind, entries in [('package', package), ('engine', engine)]}))
            self.player_inputs(inputs / 'players')
            out = Path(td) / 'site'
            with patch.object(pages.release, 'identity', return_value=self.info), \
                    patch.object(pages, 'changelog_entry', return_value=dict(new=[], changed=[], fixed=[])), \
                    patch.object(pages, 'page', side_effect=lambda dest: dest.mkdir()):
                pages.build(SimpleNamespace(tag='v1.2.3', inputs=inputs, out=out))
            cur = json.loads((out / 'engine/current.json').read_text())
            self.assertEqual(sorted(cur['players']), sorted(pages.PLAYERS))
            for entry in cur['players'].values():
                self.assertTrue((out / entry['url']).is_file())
            # outside the engine's own folder (immutable, checked against its plan)
            self.assertFalse(any('players' in p.parts for p in (out / 'engine').rglob('*')))

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
