"""The desktop patcher's logic without a window (tools/patcher/desktop.py) and dwpatch's interface for it.
Synthetic images and packages only: no disc, no network."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import desktop  # noqa: E402
import dwpatch as dw  # noqa: E402

RAW = 2352


def image(boot, sector=RAW, sectors=24, extra=b''):
    """A minimal ISO 9660 image whose SYSTEM.CNF boots `boot` (raw Mode 2 or 2048-byte sectors)."""
    def data_sector(payload):
        payload = payload.ljust(2048, b'\0')
        if sector == RAW:
            return b'\0' * 15 + b'\x02' + b'\0' * 8 + payload + b'\0' * 280
        return payload
    cnf = f'BOOT = cdrom:\\{boot};1\r\nTCB = 4\r\n'.encode()
    rec = bytearray(34 + 12)
    rec[0] = len(rec); rec[2:6] = (20).to_bytes(4, 'little'); rec[10:14] = len(cnf).to_bytes(4, 'little')
    rec[32] = 12; rec[33:45] = b'SYSTEM.CNF;1'
    pvd = bytearray(2048); pvd[0] = 1; pvd[1:6] = b'CD001'
    pvd[158:162] = (18).to_bytes(4, 'little'); pvd[166:170] = (2048).to_bytes(4, 'little')
    sectors_data = [b''] * sectors
    sectors_data[16] = bytes(pvd); sectors_data[18] = bytes(rec); sectors_data[20] = cnf
    sectors_data[22] = extra
    return b''.join(data_sector(s) for s in sectors_data)


class Images(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return str(p)

    def test_boot_name_forms(self):
        self.assertEqual(desktop.boot_and_layout(self.write('a.bin', image('SLUS_010.32'))), ('SLUS_010.32', RAW))
        self.assertEqual(desktop.boot_and_layout(self.write('b.iso', image('SLES_039.36', 2048))), ('SLES_039.36', 2048))
        self.assertEqual(desktop.boot_and_layout(self.write('c.bin', b'\0' * RAW * 20)), (None, None))

    def test_identify_messages(self):
        cases = [('dw1.bin', image('SLUS_010.32'), 'why.badDump'),        # Digimon World, not the redump dump
                 ('dw1.iso', image('SLUS_010.32', 2048), 'why.isoDw1'),
                 ('other.bin', image('SCUS_944.26'), 'why.otherGame'),
                 ('best.bin', image('SLPS_917.12'), 'why.useInstead'),   # PlayStation the Best: no supported release
                 ('junk.bin', b'\1' * 5000, 'why.notImage')]
        for name, data, key in cases:
            with self.subTest(name=name), self.assertRaises(desktop.Problem) as e:
                desktop.identify(self.write(name, data))
            self.assertEqual(e.exception.key, key)
        # a known release whose support is planned (none today: World 3 USA was the last, so a registry that says
        # so stands in) names the releases that work
        reg = json.loads(json.dumps(desktop.registry()))
        w3us = next(d for d in reg['variants'] if d['id'] == 'dw3-us')
        w3us.update(supported=False, soon=True, instead=['Digimon World 2003 (Europe)',
                                                         'DigimonWorld 3: Aratanaru Bouken no Tobira (Japan)'])
        with patch.object(desktop, '_REGISTRY', reg), self.assertRaises(desktop.Problem) as e:
            desktop.identify(self.write('w3us.bin', image('SLUS_014.36')))
        self.assertEqual(e.exception.key, 'why.notYet')
        self.assertEqual(e.exception.params, dict(release='Digimon World 3 (USA)', instead=[
            'Digimon World 2003 (Europe)', 'DigimonWorld 3: Aratanaru Bouken no Tobira (Japan)']))
        for name, key in (('x.chd', 'why.chd'), ('x.7z', 'app.archive'), ('x.part2.rar', 'app.archive'),
                          ('x.ecm', 'app.convert'), ('x.pbp', 'app.convert')):
            with self.subTest(name=name), self.assertRaises(desktop.Problem) as e:
                desktop.identify(self.write(name, b'x'))
            self.assertEqual(e.exception.key, key)

    def test_source_disc_not_redump_is_checked_by_files(self):
        r = desktop.identify(self.write('dcb.iso', image('SLUS_013.28', 2048)))
        self.assertEqual((r['game'], r['release'], r['how']), ('dcb', 'dcb', 'files'))

    def test_world_3_usa_is_a_source(self):
        r = desktop.identify(self.write('w3us.bin', image('SLUS_014.36')))
        self.assertEqual((r['game'], r['release']), ('dw2003', 'dw3-us'))

    def test_redump_match_and_cue(self):
        data = image('SLUS_011.93', extra=b'world two')
        path = self.write('Digimon World 2 (USA).bin', data)
        reg = json.loads(json.dumps(desktop.registry()))
        reg['discs'][2].update(size=len(data), sha1=hashlib.sha1(data).hexdigest())
        cue = self.dir / 'disc.cue'
        cue.write_text('FILE "Digimon World 2 (USA).bin" BINARY\n  TRACK 01 MODE2/2352\n', encoding='utf-8')
        with patch.object(desktop, '_REGISTRY', reg):
            r = desktop.identify(str(cue))
        self.assertEqual((r['game'], r['release'], r['how'], r['image']), ('dw2', 'dw2', 'redump', path))
        self.assertEqual(desktop.source_disc_args({'dcb': r, 'dw2': r, 'dw2003': r})['dw2'], path)

    def test_cue_problems(self):
        cue = self.dir / 'a.cue'
        cue.write_text('FILE "missing.bin" BINARY\n')
        with self.assertRaises(desktop.Problem) as e:
            desktop.identify(str(cue))
        self.assertEqual((e.exception.key, e.exception.params), ('why.cueOnly', {'file': 'missing.bin'}))
        cue.write_text('FILE "a (Track 1).bin" BINARY\nFILE "a (Track 2).bin" BINARY\n')
        with self.assertRaises(desktop.Problem) as e:
            desktop.identify(str(cue))
        self.assertEqual(e.exception.key, 'why.track')

    def test_sort_files_last_wins_duplicates_once_problems_listed(self):
        a = self.write('a.iso', image('SLUS_013.28', 2048))
        b = self.write('b.iso', image('SLES_039.00', 2048, extra=b'eu'))
        bad = self.write('c.bin', image('SCUS_944.26'))
        found, problems = desktop.sort_files([a, b, a, bad])
        self.assertEqual(found['dcb']['path'], b)
        self.assertEqual([(p, e.key) for p, e in problems], [(bad, 'why.otherGame')])

    def test_cancel_while_hashing(self):
        stop = threading.Event(); stop.set()
        with self.assertRaises(desktop.Problem) as e:
            desktop.identify(self.write('a.iso', image('SLUS_013.28', 2048)), cancel=stop)
        self.assertEqual(e.exception.key, 'cancelled')


class Settings(unittest.TestCase):
    def test_remembered_discs_rechecked_by_size_and_time(self):
        with tempfile.TemporaryDirectory() as td:
            disc = Path(td) / 'World 2.bin'
            disc.write_bytes(b'one')
            size, mtime = desktop.stamp(str(disc))
            entry = dict(path=str(disc), image=str(disc), size=size, mtime_ns=mtime, sha1='x', release='dw2')
            c = desktop.Config(os.path.join(td, 'settings.json'))
            c.remember_disc('dw2', entry)
            c.remember_disc('dcb', dict(entry, path=str(Path(td) / 'gone.cue'), image=str(Path(td) / 'gone.bin')))
            c2 = desktop.Config(os.path.join(td, 'settings.json'))
            found = c2.remembered_discs()
            self.assertIsNone(found['dw2'][1])
            self.assertEqual(found['dcb'][1], 'missing')
            disc.write_bytes(b'two!')
            self.assertEqual(desktop.Config(c.path).remembered_discs()['dw2'][1], 'changed')
            self.assertEqual(desktop.Config(c.path).data['discs'], {})      # (a changed disc is forgotten)

    def test_broken_settings_file_starts_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'settings.json')
            Path(path).write_text('{not json')
            self.assertEqual(desktop.Config(path).data, {'discs': {}})

    def test_folders_follow_the_platform_or_override(self):
        with patch.dict(os.environ, HORIZON_PATCHER_HOME='/x'):
            self.assertEqual(desktop.cache_dir(), os.path.join('/x', 'cache'))
        with patch.dict(os.environ, {'HORIZON_PATCHER_HOME': ''}), patch.object(desktop.os, 'name', 'nt'), \
                patch.dict(os.environ, APPDATA='C:\\R', LOCALAPPDATA='C:\\L'):
            self.assertTrue(desktop.config_dir().startswith('C:\\R'))
            self.assertTrue(desktop.cache_dir().startswith('C:\\L'))


def tarball(path, files, extra=()):
    with tarfile.open(path, 'w:gz') as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name); info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        for info in extra:
            t.addfile(info)


PACKAGE = {'manifest.json': json.dumps(dict(version='9.9.9', date='2030-01-01', commit='c' * 40)).encode(),
           'dwpatch.py': b'GUI_API = 1\ndef apply_disc(*a, **k): return {}\n', 'bundle/tools/x.py': b'print(1)\n'}


def sums(files):
    return {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}


class Packages(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        self.env = patch.dict(os.environ, HORIZON_PATCHER_HOME=str(self.dir / 'home'))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.td.cleanup()

    def test_unpack_checks_every_file(self):
        tar = self.dir / 'p.tar.gz'
        tarball(tar, PACKAGE)
        out = desktop.unpack_package(str(tar), str(self.dir / 'ok'), sums(PACKAGE))
        self.assertEqual(desktop.package_info(out)['version'], '9.9.9')
        bad = dict(sums(PACKAGE), **{'dwpatch.py': '0' * 64})
        for name, checks in (('wrong', bad), ('missing', dict(sums(PACKAGE), **{'more.txt': '0' * 64})),
                             ('extra', {k: v for k, v in sums(PACKAGE).items() if k != 'bundle/tools/x.py'})):
            with self.subTest(name), self.assertRaises(desktop.Problem):
                desktop.unpack_package(str(tar), str(self.dir / name), checks)
            self.assertFalse((self.dir / name).exists())
            self.assertFalse((self.dir / (name + '.unpacking')).exists())

    def test_unpack_refuses_links_and_escapes(self):
        link = tarfile.TarInfo('link'); link.type = tarfile.SYMTYPE; link.linkname = '/etc/passwd'
        for name, files, extra in (('escape', dict(PACKAGE, **{'../x': b'x'}), ()),
                                   ('absolute', dict(PACKAGE, **{'/tmp/x': b'x'}), ()),
                                   ('link', PACKAGE, (link,))):
            tar = self.dir / f'{name}.tar.gz'
            tarball(tar, files, extra)
            with self.subTest(name), self.assertRaises(desktop.Problem):
                desktop.unpack_package(str(tar), str(self.dir / name))
            self.assertFalse((self.dir / name).exists())

    def test_install_release_downloads_verifies_and_prunes(self):
        tar = self.dir / 'horizon-package.tar.gz'
        tarball(tar, PACKAGE)
        checks = self.dir / 'horizon-checksums.json'
        checks.write_text(json.dumps(dict(package=sums(PACKAGE), engine={})))
        digest = 'sha256:' + hashlib.sha256(tar.read_bytes()).hexdigest()

        def fake_download(url, dest, progress=None, cancel=None, size=None):
            Path(dest).write_bytes(Path(url).read_bytes())
            return dest
        rel = dict(tag='v9.9.9', version='9.9.9', assets={
            'horizon-package.tar.gz': dict(url=str(tar), size=tar.stat().st_size, digest=digest),
            'horizon-checksums.json': dict(url=str(checks), size=None, digest=None)})
        with patch.object(desktop, 'download', fake_download):
            info = desktop.install_release(rel)
            self.assertEqual(info['version'], '9.9.9')
            self.assertEqual([p['name'] for p in desktop.cached_packages()], ['v9.9.9'])
            bad = json.loads(json.dumps(rel)); bad['tag'] = 'v9.9.10'
            bad['assets']['horizon-package.tar.gz']['digest'] = 'sha256:' + '0' * 64
            with self.assertRaises(desktop.Problem):
                desktop.install_release(bad)
            self.assertEqual([p['name'] for p in desktop.cached_packages()], ['v9.9.9'])
            del bad['assets']['horizon-package.tar.gz']
            with self.assertRaises(desktop.Problem) as e:
                desktop.install_release(bad)
            self.assertEqual(e.exception.key, 'app.noPackage')

    def test_install_file_uses_checksums_next_to_it(self):
        tar = self.dir / 'horizon-package.tar.gz'
        tarball(tar, PACKAGE)
        self.assertFalse(desktop.install_file(str(tar))['verified'])
        (self.dir / 'horizon-checksums.json').write_text(json.dumps(dict(package=sums(PACKAGE))))
        tarball(tar, dict(PACKAGE, **{'README.md': b'new'}))
        with self.assertRaises(desktop.Problem):
            desktop.install_file(str(tar))
        tarball(tar, PACKAGE)
        self.assertEqual(desktop.install_file(str(tar))['version'], '9.9.9')

    def test_release_info_and_versions(self):
        r = desktop.release_info(dict(tag_name='v0.1.0', name='Horizon 0.1.0', assets=[
            dict(name='horizon-package.tar.gz', browser_download_url='https://x/p', size=5, digest='sha256:ab')]))
        self.assertEqual((r['version'], r['assets']['horizon-package.tar.gz']['url']), ('0.1.0', 'https://x/p'))
        self.assertGreater(desktop.version_key('v0.0.10'), desktop.version_key('0.0.9'))
        self.assertLess(desktop.version_key('junk'), desktop.version_key('0.0.1'))

    def test_latest_release_without_the_api(self):
        import urllib.error

        class Page:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def geturl(self): return 'https://github.com/o/r/releases/tag/v1.2.3'

        def fake(url, *a, **k):
            if 'api.github.com' in url:
                raise urllib.error.HTTPError(url, 403, 'rate limit exceeded', {}, None)
            self.assertEqual(url, 'https://github.com/o/r/releases/latest')
            return Page()
        with patch.object(desktop, '_open', fake):
            r = desktop.latest_release('o/r')
        self.assertEqual(r['version'], '1.2.3')
        self.assertEqual(r['assets']['horizon-package.tar.gz']['url'],
                         'https://github.com/o/r/releases/download/v1.2.3/horizon-package.tar.gz')

    def test_load_patcher_requires_the_interface(self):
        new, old = self.dir / 'new', self.dir / 'old'
        for folder, code in ((new, PACKAGE['dwpatch.py']), (old, b'X = 1\n')):
            folder.mkdir()
            (folder / 'dwpatch.py').write_bytes(code)
            (folder / 'manifest.json').write_bytes(PACKAGE['manifest.json'])
        saved = sys.modules.get('dwpatch')
        try:
            self.assertEqual(desktop.load_patcher(str(new)).GUI_API, 1)
            with self.assertRaises(desktop.Problem) as e:
                desktop.load_patcher(str(old))
            self.assertEqual(e.exception.key, 'app.packageOld')
        finally:
            sys.modules['dwpatch'] = saved


class Interface(unittest.TestCase):
    """dwpatch's interface for the app: CANCEL, status(), apply_disc()."""
    def tearDown(self):
        dw.CANCEL = None
        dw.SCREEN = None

    def test_cancel_stops_at_the_next_tick_and_the_command_line_never_does(self):
        with tempfile.TemporaryDirectory() as td:
            sc = dw.Screen([('check', 'checking', 1), ('write', 'writing', 1)], os.path.join(td, 'log'),
                           out=dw._Null())
            sc.start('check'); sc.part(0.5)
            dw.CANCEL = threading.Event()
            sc.part(0.6)
            dw.CANCEL.set()
            for call in (lambda: sc.part(0.7), lambda: sc.start('write'), lambda: sc.write_raw('x\n'),
                         lambda: dw.Progress('x', 10)(1)):
                with self.assertRaises(dw.Stopped):
                    call()
            sc.done(ok=False); sc.close()

    def test_status(self):
        self.assertIsNone(dw.status())
        with tempfile.TemporaryDirectory() as td:
            dw.SCREEN = dw.Screen([('check', 'checking your disc', 1), ('write', 'writing', 3)],
                                  os.path.join(td, 'log'), out=dw._Null())
            dw.SCREEN.start('write')
            st = dw.status()
            self.assertEqual((st['phase'], st['words']), ('write', 'writing'))
            self.assertAlmostEqual(st['fraction'], 0.25, places=1)
            dw.SCREEN.close()

    def test_apply_disc_raises_the_players_message_and_prints_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            fake = os.path.join(td, 'not a disc.bin')
            Path(fake).write_bytes(b'\0' * 5000)
            rel = os.path.join(td, 'rel')
            os.makedirs(rel)
            manifest = dict(format=3, default='everything', title='Horizon', version='1', date='2030-01-01', commit='c', source_discs=['dcb', 'dw2', 'dw2003'], python_min=[3, 10],
                            variants={'everything': dict(local={'builder': 'derive'}, output={'name': 'Horizon'},
                                                         description='everything')},
                            bases={'us': dict(dw.ORIGINAL)})
            Path(rel, 'manifest.json').write_text(json.dumps(manifest))
            out = io.StringIO()
            with patch.object(sys, 'stdout', out), self.assertRaises(dw.PatchError) as e:
                dw.apply_disc(fake, dict(dcb=fake, dw2=fake, dw2003=fake), output=os.path.join(td, 'o'), release=rel)
            self.assertEqual(out.getvalue(), '')
            self.assertIsNone(dw.SCREEN)
            self.assertIn('ERROR: not a disc.bin has 5000 bytes', Path(e.exception.log).read_text(encoding='utf-8'))
            self.assertEqual(e.exception.log, os.path.join(td, 'o', 'Horizon.log'))


class Shim(unittest.TestCase):
    def run_shim(self, args, cwd=None):
        code = ('import sys; sys.path.insert(0, %r); import desktop; sys.exit(desktop.python_shim(sys.argv[1:]))'
                % str(Path(__file__).resolve().parent / 'patcher'))
        env = dict(os.environ, HORIZON_SHIM_TEST='1')
        return subprocess.run([sys.executable, '-c', code, *args], cwd=cwd, env=env, capture_output=True, text=True)

    def test_three_forms(self):
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td, 'spaced dir', 'mod')
            pkg.mkdir(parents=True)
            (pkg / '__init__.py').write_text('')
            (pkg / '__main__.py').write_text('import sys; print("module", sys.argv[1:]); sys.exit(3)')
            script = Path(td, 'spaced dir', 'tool.py')
            script.write_text('import sys; print("script", sys.argv[1:])')
            r = self.run_shim(['-c', 'import sys; print("code", sys.argv)', 'a b'])
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "code ['-c', 'a b']"))
            r = self.run_shim(['-m', 'mod', 'x'], cwd=str(pkg.parent))
            self.assertEqual((r.returncode, r.stdout.strip()), (3, "module ['x']"))
            r = self.run_shim([str(script), 'y'])
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "script ['y']"))
            r = self.run_shim(['-c', 'raise ValueError("boom")'])
            self.assertEqual(r.returncode, 1)
            self.assertIn('ValueError: boom', r.stderr)
            self.assertIsNone(desktop.python_shim(['--self-test']))


class Strings(unittest.TestCase):
    def test_every_language_has_every_key_and_placeholder(self):
        import re
        table = json.loads((Path(__file__).resolve().parent / 'patcher/app/i18n.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(table), sorted(['en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans']))
        for lang, strings in table.items():
            self.assertEqual(set(strings), set(table['en']), lang)
            for k, v in strings.items():
                self.assertEqual(set(re.findall(r'\{\w+\}', v)), set(re.findall(r'\{\w+\}', table['en'][k])),
                                 (lang, k))
        used = set()
        for f in ('gui.py', 'desktop.py'):
            used |= set(re.findall(r"'(app\.[A-Za-z.]+[A-Za-z])'", (Path(__file__).resolve().parent / 'patcher' / f)
                                   .read_text(encoding='utf-8')))
        self.assertEqual(used - set(table['en']) - {'app.log'}, set())          # (app.log: a file name)


if __name__ == '__main__':
    unittest.main()
