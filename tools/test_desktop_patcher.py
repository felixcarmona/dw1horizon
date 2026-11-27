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
import struct
import zlib
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import discformats  # noqa: E402
import desktop  # noqa: E402
import dwpatch as dw  # noqa: E402
import setup_exe  # noqa: E402
import mac_app  # noqa: E402
import linux_run  # noqa: E402
import plistlib  # noqa: E402
import stat  # noqa: E402
import zipfile  # noqa: E402

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


def pbp(data, stored=False, tag=b'PSISOIMG0000'):
    """Synthetic single-track PBP; last block is padded like popstation."""
    psar = 0x28
    header = bytearray(psar + 0x100000)
    header[:4] = b'\0PBP'
    struct.pack_into('<I', header, 0x24, psar)
    header[psar:psar + len(tag)] = tag
    frames = len(data) // RAW + 150
    minute, rest = divmod(frames, 60 * 75)
    second, frame = divmod(rest, 75)
    header[psar + 0x802] = 0xa2
    header[psar + 0x807:psar + 0x80a] = bytes((x // 10 * 16 + x % 10) for x in (minute, second, frame))
    payload = bytearray()
    for i, start in enumerate(range(0, len(data), discformats.BLOCK)):
        raw = data[start:start + discformats.BLOCK].ljust(discformats.BLOCK, b'\0')
        enc = zlib.compressobj(wbits=-15)
        block = raw if stored is True or (stored == 'mixed' and i % 2 == 0) else enc.compress(raw) + enc.flush()
        struct.pack_into('<IH', header, psar + 0x4000 + i * 32, len(payload), len(block))
        payload.extend(block)
    return header + payload


class Images(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        self.env = patch.dict(os.environ, HORIZON_PATCHER_HOME=str(self.dir / 'home'))
        self.env.start()

    def tearDown(self):
        desktop.CONVERSIONS.close()
        self.env.stop()
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
        for name, key in (('x.chd', 'app.chdUnsupported'), ('x.7z', 'app.archive'), ('x.part2.rar', 'app.archive'),
                          ('x.ecm', 'app.convert'), ('x.pbp', 'app.pbpEncrypted')):
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


class PbpImages(unittest.TestCase):
    setUp = Images.setUp
    tearDown = Images.tearDown
    write = Images.write

    def test_roundtrip_stored_deflated_and_partial_last_block(self):
        data = image('SLUS_013.28', sectors=37)
        for stored in (False, True, 'mixed'):
            src = self.write('renamed.img', pbp(data, stored))
            dst = self.dir / 'decoded.bin'
            progress = []
            self.assertEqual(discformats.sniff(src), 'pbp')
            discformats.decode_pbp(src, dst, progress.append)
            self.assertEqual(dst.read_bytes(), data)
            self.assertEqual(progress[-1], 1)
            result = desktop.identify(src)
            self.assertEqual(result['path'], src)
            self.assertEqual(Path(result['image']).read_bytes(), data)
            self.assertEqual(result['game'], 'dcb')
            self.assertEqual(result['sha1'], hashlib.sha1(data).hexdigest())

    def test_reuse_mtime_and_remembered_source(self):
        src = self.write('disc.pbp', pbp(image('SLUS_013.28')))
        first = desktop.identify(src)
        with patch.object(discformats, 'decode_pbp', wraps=discformats.decode_pbp) as decode:
            self.assertEqual(desktop.identify(src)['image'], first['image'])
            decode.assert_not_called()
            c = desktop.Config(str(self.dir / 'settings.json'))
            c.remember_disc('dcb', first)
            self.assertIsNone(c.remembered_discs()['dcb'][1])
            st = os.stat(src)
            os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
            self.assertEqual(c.remembered_discs()['dcb'][1], 'changed')
            second = desktop.identify(src)
            self.assertEqual(decode.call_count, 1)
            self.assertFalse(Path(first['image']).exists())
        desktop.CONVERSIONS.close()
        self.assertFalse(Path(second['image']).exists())
        c.remember_disc('dcb', second)
        self.assertEqual(c.remembered_discs()['dcb'][1], 'convert')

    def test_size_change_invalidates_conversion_even_with_same_mtime(self):
        src = self.write('disc.pbp', pbp(image('SLUS_013.28')))
        first = desktop.identify(src)
        st = os.stat(src)
        with open(src, 'ab') as f:
            f.write(b'padding')
        os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns))
        with patch.object(discformats, 'decode_pbp', wraps=discformats.decode_pbp) as decode:
            desktop.identify(src)
            decode.assert_called_once()
        self.assertFalse(Path(first['image']).exists())

    def test_api_conversion_is_quiet_and_cleans_up_on_failure(self):
        src = self.write('disc.pbp', pbp(image('SLUS_013.28')))
        paths = []
        def apply(args):
            paths.append(dw.resolve_bin(args.disc))
            raise dw.PatchError('stand-in failure')
        output = io.StringIO()
        with patch.object(dw, 'cmd_apply', side_effect=apply), patch.object(sys, 'stdout', output):
            with self.assertRaisesRegex(dw.PatchError, 'stand-in failure'):
                dw.apply_disc(src, {})
        self.assertEqual(output.getvalue(), '')
        self.assertFalse(Path(paths[0]).exists())

    def test_errors_and_failed_identification_remove_temporaries(self):
        good = pbp(image('SLUS_013.28'))
        corrupt = bytearray(good)
        corrupt[0x28 + 0x100000:] = b'x' * (len(corrupt) - 0x28 - 0x100000)
        for data, key in ((pbp(image('SLUS_013.28'), tag=b'PSTITLEIMG'), 'app.pbpMulti'),
                          (pbp(image('SLUS_013.28'), tag=b'ENCRYPTED'), 'app.pbpEncrypted'),
                          (corrupt, 'app.pbpEncrypted'), (good[:-1], 'app.pbpEncrypted'),
                          (pbp(image('SCUS_944.26')), 'why.otherGame')):
            with self.subTest(key=key), self.assertRaises(desktop.Problem) as caught:
                desktop.identify(self.write('bad.pbp', data))
            self.assertEqual(caught.exception.key, key)
            self.assertEqual(list(Path(desktop.cache_dir()).rglob('*.bin')), [])

    def test_space_and_cancel_during_conversion(self):
        src = self.write('disc.pbp', pbp(image('SLUS_013.28', sectors=50)))
        with patch.object(discformats.shutil, 'disk_usage', return_value=Mock(free=0)):
            with self.assertRaises(desktop.Problem) as caught:
                desktop.identify(src)
        self.assertEqual(caught.exception.key, 'app.pbpSpace')
        stop = threading.Event()
        def progress(path, fraction):
            stop.set()
        with self.assertRaises(desktop.Problem) as caught:
            desktop.identify(src, cancel=stop, converting=progress)
        self.assertEqual(caught.exception.key, 'cancelled')
        self.assertEqual(list(Path(desktop.cache_dir()).rglob('*.bin')), [])

    def test_converted_base_still_requires_its_exact_hash(self):
        data = image('SLUS_010.32')
        src = self.write('base.pbp', pbp(data))
        reg = json.loads(json.dumps(desktop.registry()))
        reg['discs'][0].update(size=len(data), sha1=hashlib.sha1(data).hexdigest())
        with patch.object(desktop, '_REGISTRY', reg):
            self.assertEqual(desktop.identify(src)['how'], 'redump')
        with self.assertRaises(desktop.Problem) as caught:
            desktop.identify(src)
        self.assertEqual(caught.exception.key, 'why.badDump')
        self.assertEqual(list(Path(desktop.cache_dir()).rglob('*.bin')), [])

    def test_magic_for_unsupported_and_cue(self):
        for magic, kind in ((b'MComprHD', 'chd'), (b'ECM\0', 'ecm'),
                            (b'FILE "disc.bin" BINARY\n', 'cue')):
            self.assertEqual(discformats.sniff(self.write('renamed.bin', magic)), kind)

    def test_cli_resolves_pbp_and_shipped_module(self):
        data = image('SLUS_013.28')
        src = self.write('disc.pbp', pbp(data))
        try:
            converted = dw.resolve_bin(src)
            self.assertEqual(Path(converted).read_bytes(), data)
            self.assertEqual(dw.resolve_bin(src), converted)
            dest = self.dir / 'release'
            dest.mkdir()
            dw.copy_release_frontend(str(dest))
            result = subprocess.run([sys.executable, '-c',
                                     'import dwpatch; print(dwpatch.boot_name(dwpatch.resolve_bin(' + repr(src) + ')))'],
                                    cwd=dest, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('SLUS_013.28', result.stdout)
        finally:
            if dw._CONVERSIONS:
                dw._CONVERSIONS.close()


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


class TaggedSelfTest(unittest.TestCase):
    def prepare(self, root, files=PACKAGE, checksums=None, tag='v9.9.9', commit='c' * 40):
        from app import prepare_selftest as ci

        def download(command, check):
            self.assertTrue(check)
            self.assertEqual(command[:4], ['gh', 'release', 'download', tag])
            self.assertEqual(command[6:], ['--pattern', desktop.PACKAGE_ASSET,
                                          '--pattern', desktop.CHECKSUMS_ASSET])
            out = Path(command[5])
            tarball(out / desktop.PACKAGE_ASSET, files)
            (out / desktop.CHECKSUMS_ASSET).write_text(json.dumps(
                {'package': sums(files) if checksums is None else checksums}))

        with patch.object(ci.subprocess, 'run', side_effect=download):
            return ci.prepare(tag, root / 'assets', commit)

    def test_draft_tag_package_is_verified_without_latest(self):
        with tempfile.TemporaryDirectory() as td:
            folder = self.prepare(Path(td))
            self.assertEqual(desktop.package_info(folder)['version'], '9.9.9')

    def test_bad_checksum_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(desktop.Problem):
                self.prepare(Path(td), checksums=dict(sums(PACKAGE), **{'dwpatch.py': '0' * 64}))

    def test_other_version_or_commit_is_rejected(self):
        for change in (dict(tag='v9.9.8'), dict(commit='d' * 40)):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(ValueError, 'version or commit'):
                    self.prepare(Path(td), **change)

    def test_missing_checksums_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'missing package checksums'):
                self.prepare(Path(td), checksums={})


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

    def test_unpack_refuses_case_collisions_on_every_platform(self):
        for first, second in (('bundle/names.dws', 'bundle/NAMES.dws'),
                              ('bundle/Tools/a.py', 'bundle/tools/b.py'),
                              ('BUNDLE', 'bundle/tools/b.py')):
            with self.subTest(first=first, second=second):
                tar = self.dir / 'collision.tar.gz'
                files = dict(PACKAGE, **{first: b'one', second: b'two'})
                tarball(tar, files)
                dest = self.dir / 'collision'
                with self.assertRaises(desktop.Problem) as caught:
                    desktop.unpack_package(str(tar), str(dest), sums(files))
                self.assertIn('case-colliding paths', caught.exception.params['detail'])
                self.assertFalse(dest.exists())
                self.assertFalse((self.dir / 'collision.unpacking').exists())

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

    def release_fixture(self, files=PACKAGE):
        tar = self.dir / desktop.PACKAGE_ASSET
        tarball(tar, files)
        checks = self.dir / desktop.CHECKSUMS_ASSET
        checks.write_text(json.dumps(dict(package=sums(files))))
        return dict(tag='v9.9.9', assets={
            desktop.PACKAGE_ASSET: dict(url=str(tar), size=tar.stat().st_size,
                                       digest='sha256:' + hashlib.sha256(tar.read_bytes()).hexdigest()),
            desktop.CHECKSUMS_ASSET: dict(url=str(checks))})

    @staticmethod
    def copy_download(url, dest, *args, **kwargs):
        Path(dest).write_bytes(Path(url).read_bytes())
        return dest

    def test_cache_refresh_and_legacy_cache(self):
        for legacy in (False, True):
            for change in ('unchanged', 'changed', 'removed'):
                with self.subTest(legacy=legacy, change=change), patch.object(
                        desktop, 'download', side_effect=self.copy_download) as download:
                    info = desktop.install_release(self.release_fixture())
                    folder = Path(info['folder'])
                    if legacy:
                        (folder / desktop.PACKAGE_RECORD).unlink()
                        (folder / '__pycache__').mkdir(exist_ok=True)
                        (folder / '__pycache__/dwpatch.pyc').write_bytes(b'generated')
                    files = dict(PACKAGE)
                    if change == 'changed':
                        files['dwpatch.py'] = b'corrected reader'
                    elif change == 'removed':
                        del files['bundle/tools/x.py']
                    rel = self.release_fixture(files)
                    download.reset_mock()
                    self.assertEqual(desktop.install_release(rel), info)
                    self.assertEqual([c.args[0] for c in download.call_args_list],
                                     [rel['assets'][desktop.CHECKSUMS_ASSET]['url']] +
                                     ([] if change == 'unchanged' else [rel['assets'][desktop.PACKAGE_ASSET]['url']]))
                    self.assertEqual((folder / 'dwpatch.py').read_bytes(), files['dwpatch.py'])
                    self.assertEqual((folder / 'bundle/tools/x.py').exists(), change != 'removed')
                    self.assertEqual(json.loads((folder / desktop.PACKAGE_RECORD).read_text()), sums(files))
                    self.assertEqual([p.name for p in folder.parent.iterdir()], ['v9.9.9'])

    def test_failed_refresh_preserves_old_package(self):
        for failure in ('offline', 'download', 'checksum', 'rename', 'cancel'):
            with self.subTest(failure=failure):
                with patch.object(desktop, 'download', side_effect=self.copy_download):
                    info = desktop.install_release(self.release_fixture())
                rel = self.release_fixture(dict(PACKAGE, **{'dwpatch.py': b'corrected reader'}))
                if failure == 'checksum':
                    Path(rel['assets'][desktop.CHECKSUMS_ASSET]['url']).write_text(
                        json.dumps(dict(package=dict(sums(PACKAGE), **{'dwpatch.py': '0' * 64}))))

                def download(url, dest, *args, **kwargs):
                    if failure == 'offline':
                        raise OSError('offline')
                    if url == rel['assets'][desktop.PACKAGE_ASSET]['url']:
                        if failure == 'download':
                            Path(dest + '.part').write_bytes(b'incomplete')
                            raise OSError('connection lost')
                        if failure == 'cancel':
                            raise desktop.Problem('cancelled')
                    return self.copy_download(url, dest)

                replace = os.replace

                def rename(src, dst):
                    if failure == 'rename' and Path(src).name == 'package':
                        raise OSError('rename failed')
                    return replace(src, dst)

                with patch.object(desktop, 'download', side_effect=download), patch.object(
                        desktop.os, 'replace', side_effect=rename):
                    if failure == 'cancel':
                        with self.assertRaises(desktop.Problem):
                            desktop.install_release(rel)
                    else:
                        with self.assertLogs('desktop') as logs:
                            self.assertEqual(desktop.install_release(rel), info)
                        self.assertIn('using cached package', logs.output[-1])
                folder = Path(info['folder'])
                self.assertEqual((folder / 'dwpatch.py').read_bytes(), PACKAGE['dwpatch.py'])
                self.assertEqual(json.loads((folder / desktop.PACKAGE_RECORD).read_text()), sums(PACKAGE))
                self.assertEqual([p.name for p in folder.parent.iterdir()], ['v9.9.9'])

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


class PbpGuiFlow(unittest.TestCase):
    def test_quit_cancels_and_waits_for_conversion_before_cleanup(self):
        import gui
        app = gui.App.__new__(gui.App)
        app.busy = 'check'
        app.cancel = threading.Event()
        app.root = Mock()
        app.worker = Mock()
        app.worker.is_alive.side_effect = [True, False]
        with patch.object(desktop.CONVERSIONS, 'close') as cleanup:
            app.close()
            self.assertTrue(app.cancel.is_set())
            cleanup.assert_not_called()
            app.root.destroy.assert_not_called()
            app.root.after.assert_called_once_with(100, app.close)
            app.close()
            cleanup.assert_called_once()
            app.root.destroy.assert_called_once()

    def test_original_path_sets_default_output_and_restore_reconverts(self):
        import gui
        app = gui.App.__new__(gui.App)
        app.config = Mock()
        app.config.get.return_value = None
        original = os.path.join(tempfile.gettempdir(), 'discs', 'disc.pbp')
        entry = dict(path=original, image='temporary-cache/disc.bin')
        app.slots = {'us': entry}
        self.assertEqual(app.output_folder(), desktop.default_output(original))
        app.slots = {}
        app.notes = {}
        app.config.remembered_discs.return_value = {'us': (entry, 'convert')}
        app._refresh = Mock()
        app._check = Mock()
        with patch.object(desktop, 'cached_packages', return_value=[]):
            app._restore()
        app._check.assert_called_once_with([original])
        self.assertEqual(app.notes, {})


class HorizonPlay(unittest.TestCase):
    """The Play button (docs/player.md): shown when the app carries Horizon Play and a disc was built."""

    def test_player_program_found_in_the_app_data(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(desktop, 'resource', side_effect=lambda *p: os.path.join(d, *p)):
                self.assertIsNone(desktop.player_program())
                if sys.platform == 'darwin':
                    parts = ('player', 'Horizon Play.app', 'Contents', 'MacOS', 'horizon-play')
                else:
                    parts = ('player', 'horizon-play.exe' if os.name == 'nt' else 'horizon-play')
                os.makedirs(os.path.join(d, *parts[:-1]))
                open(os.path.join(d, *parts), 'wb').close()
                self.assertEqual(desktop.player_program(), os.path.join(d, *parts))

    def test_play_starts_the_program_on_the_disc(self):
        with patch.object(desktop, 'player_program', return_value=os.path.join('app', 'player', 'horizon-play')), \
                patch('subprocess.Popen') as popen:
            desktop.play('disc.cue')
        args = popen.call_args[0][0]
        self.assertEqual(args, [os.path.join('app', 'player', 'horizon-play'), os.path.abspath('disc.cue')])
        with patch.object(desktop, 'player_program', return_value=None):
            with self.assertRaises(FileNotFoundError):
                desktop.play('disc.cue')

    def test_restore_offers_play_for_the_last_disc(self):
        import gui
        with tempfile.TemporaryDirectory() as d:
            cue = os.path.join(d, 'horizon.cue')
            open(cue, 'w').close()
            app = gui.App.__new__(gui.App)
            app.config = Mock()
            app.config.get.side_effect = lambda k, default=None: cue if k == 'last_disc' else default
            app.config.remembered_discs.return_value = {}
            app.slots, app.notes = {}, {}
            app._refresh = Mock()
            app._finish_buttons = Mock()
            with patch.object(desktop, 'cached_packages', return_value=[]):
                app._restore()
            app._finish_buttons.assert_called_once_with(d, None, cue)



class CacheRefreshFlow(unittest.TestCase):
    def test_check_and_build_recheck_same_release_but_keep_imported_package(self):
        import gui
        for source in ('release', 'file'):
            app = gui.App.__new__(gui.App)
            app.package = dict(version='9.9.9', source=source, folder='cached')
            app.events = Mock()
            app.t = Mock(return_value='status')
            app._job_download = Mock(return_value=app.package)
            latest = dict(version='9.9.9')
            with patch.object(desktop, 'latest_release', return_value=latest):
                app._job_latest_checked()
                self.assertEqual(app._job_download.call_count, int(source == 'release'))
                app._job_download.reset_mock()
                with patch.object(desktop, 'load_patcher', side_effect=RuntimeError('stop before applying')):
                    with self.assertRaisesRegex(RuntimeError, 'stop before applying'):
                        app._job_build('output')
                self.assertEqual(app._job_download.call_count, int(source == 'release'))


class SetupExe(unittest.TestCase):
    """The Windows setup: a template with the player's disc appended (tools/patcher/setup_exe.py)."""

    def make(self, d, cue_text=None, bin_data=b'\x01\x02' * 5000):
        d = Path(d)
        (d / 'template.exe').write_bytes(b'MZ' + bytes(range(256)) * 20)
        (d / 'my disc.bin').write_bytes(bin_data)
        (d / 'my disc.cue').write_text(cue_text or 'FILE "my disc.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        return d

    def test_trailer_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            d = self.make(d)
            out = str(d / 'out.exe')
            setup_exe.build(str(d / 'template.exe'), str(d / 'my disc.cue'), out)
            data = (d / 'out.exe').read_bytes()
            template = (d / 'template.exe').read_bytes()
            binary = (d / 'my disc.bin').read_bytes()
            size, cue_size, version = setup_exe.read_trailer(out)
            self.assertEqual((size, version), (len(binary), setup_exe.VERSION))
            self.assertEqual(data[:len(template)], template)
            self.assertEqual(data[len(template):len(template) + size], binary)
            self.assertEqual(data[-8:], b'HZSETUP1')
            cue = data[len(template) + size:len(data) - setup_exe.TRAILER.size + 0][:cue_size].decode()
            self.assertIn('FILE "Digimon World Horizon.bin" BINARY', cue)
            self.assertNotIn('my disc', cue)
            self.assertEqual(setup_exe.read_trailer(str(d / 'template.exe')), None)   # the bare template: no game
            self.assertFalse((d / 'out.exe.new').exists())

    def test_progress_reaches_the_total(self):
        with tempfile.TemporaryDirectory() as d:
            d = self.make(d)
            seen = []
            setup_exe.build(str(d / 'template.exe'), str(d / 'my disc.cue'), str(d / 'o.exe'),
                            lambda done, total: seen.append((done, total)))
            self.assertEqual(seen[-1][0], seen[-1][1])
            self.assertEqual(seen, sorted(seen))

    def test_refuses_a_cue_with_no_bin(self):
        with tempfile.TemporaryDirectory() as d:
            d = self.make(d)
            (d / 'my disc.bin').unlink()
            with self.assertRaisesRegex(setup_exe.SetupError, 'missing'):
                setup_exe.build(str(d / 'template.exe'), str(d / 'my disc.cue'), str(d / 'o.exe'))
            (d / 'my disc.cue').write_text('REM nothing\n')
            with self.assertRaisesRegex(setup_exe.SetupError, 'no FILE'):
                setup_exe.build(str(d / 'template.exe'), str(d / 'my disc.cue'), str(d / 'o.exe'))
            self.assertFalse((d / 'o.exe').exists())

    def test_refuses_several_tracks(self):
        with tempfile.TemporaryDirectory() as d:
            d = self.make(d, 'FILE "a.bin" BINARY\nFILE "b.bin" BINARY\n')
            with self.assertRaisesRegex(setup_exe.SetupError, '2 tracks'):
                setup_exe.build(str(d / 'template.exe'), str(d / 'my disc.cue'), str(d / 'o.exe'))


class Templates(unittest.TestCase):
    """The installer templates are release assets, downloaded once and cached by tag (desktop.template)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        patcher = patch.dict(os.environ, HORIZON_PATCHER_HOME=str(self.dir / 'home'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.remote = {'Horizon-Setup.exe': b'MZ template ' * 100, 'Horizon-Play.apk': b'PK apk' * 50}
        self.downloads = []

    def assets(self, digest=True):
        out = {}
        for name, data in self.remote.items():
            src = self.dir / 'remote' / name
            src.parent.mkdir(exist_ok=True)
            src.write_bytes(data)
            out[name] = dict(url=str(src), size=len(data),
                             digest='sha256:' + hashlib.sha256(data).hexdigest() if digest else None)
        return out

    def download(self, url, dest, progress=None, cancel=None, size=None):
        self.downloads.append(url)
        Path(dest).write_bytes(Path(url).read_bytes())
        if progress:
            progress(size or 1, size or 1)
        return dest

    def get(self, kind='setup', tag='v9.9.9', **kw):
        return desktop.template(kind, tag, **kw)

    def test_download_then_cache(self):
        seen = []
        with patch.object(desktop, 'release_assets', lambda tag: self.assets()), patch.object(
                desktop, 'download', self.download):
            path = self.get(progress=lambda a, b: seen.append((a, b)))
            self.assertEqual(Path(path).read_bytes(), self.remote['Horizon-Setup.exe'])
            self.assertEqual(Path(path).parent.name, 'v9.9.9')
            self.assertTrue(seen)
            self.get()                                          # a second time: from the cache
            self.assertEqual(len(self.downloads), 1)
            self.get('apk')
            self.assertEqual(len(self.downloads), 2)

    def test_offline_uses_the_cache_or_says_so(self):
        import urllib.error
        with patch.object(desktop, 'release_assets', lambda tag: self.assets()), patch.object(
                desktop, 'download', self.download):
            self.get()
        def offline(tag):
            raise urllib.error.URLError('no network')
        with patch.object(desktop, 'release_assets', offline), patch.object(desktop, 'download', self.download):
            self.assertTrue(Path(self.get()).is_file())          # cached: works offline
            with self.assertRaises(desktop.Problem) as e:        # not cached: a clear error
                self.get('apk')
            self.assertEqual(e.exception.key, 'app.templateOffline')
            self.assertEqual(e.exception.params['name'], 'Horizon-Play.apk')
        self.assertEqual(len(self.downloads), 1)

    def test_missing_asset(self):
        with patch.object(desktop, 'release_assets', lambda tag: {}):
            with self.assertRaises(desktop.Problem) as e:
                self.get('linux', tag='v0.0.1')
            self.assertEqual((e.exception.key, e.exception.params['tag']), ('app.templateMissing', 'v0.0.1'))

    def test_wrong_digest_is_refused_and_not_cached(self):
        assets = self.assets()
        assets['Horizon-Setup.exe']['digest'] = 'sha256:' + '0' * 64
        with patch.object(desktop, 'release_assets', lambda tag: assets), patch.object(desktop, 'download', self.download):
            with self.assertRaises(desktop.Problem) as e:
                self.get()
            self.assertEqual(e.exception.key, 'app.packageBad')
        self.assertFalse(list((self.dir / 'home').rglob('Horizon-Setup.exe*')))

    def test_a_corrected_asset_replaces_the_cache(self):
        with patch.object(desktop, 'release_assets', lambda tag: self.assets()), patch.object(
                desktop, 'download', self.download):
            self.get()
            self.remote['Horizon-Setup.exe'] = b'MZ corrected ' * 100
            self.assertEqual(Path(self.get()).read_bytes(), self.remote['Horizon-Setup.exe'])
        self.assertEqual(len(self.downloads), 2)

    def test_mac_template_is_unzipped_with_symlinks_and_modes(self):
        app = self.dir / 'src' / 'Horizon Play.app'
        (app / 'Contents' / 'MacOS').mkdir(parents=True)
        (app / 'Contents' / 'Resources').mkdir()
        (app / 'Contents' / 'Info.plist').write_bytes(b'<plist/>')
        (app / 'Contents' / 'MacOS' / 'horizon-play').write_bytes(b'bin')
        os.chmod(app / 'Contents' / 'MacOS' / 'horizon-play', 0o755)
        os.symlink('horizon-play', app / 'Contents' / 'MacOS' / 'alias')
        zip_path = self.dir / 'remote' / 'Horizon-Play-macOS.zip'
        zip_path.parent.mkdir(exist_ok=True)
        import mac_app as m
        # (the zip writer keeps the folder's own name as the top entry, as `ditto --keepParent` does)
        m.zip_app(str(app), str(zip_path))
        self.remote['Horizon-Play-macOS.zip'] = zip_path.read_bytes()
        with patch.object(desktop, 'release_assets', lambda tag: self.assets()), patch.object(
                desktop, 'download', self.download), patch.object(desktop, 'mac_app_template', lambda: None):
            got = Path(self.get('mac'))
            self.assertEqual(got.name, 'Horizon Play.app')
            self.assertTrue(os.path.islink(got / 'Contents' / 'MacOS' / 'alias'))
            self.assertTrue(os.access(got / 'Contents' / 'MacOS' / 'horizon-play', os.X_OK))
            self.assertEqual(Path(self.get('mac')), got)         # cached: no second download
        self.assertEqual(len(self.downloads), 1)

    def test_linux_patcher_uses_its_own_player(self):
        player = self.dir / 'player'
        player.mkdir()
        (player / 'horizon-play').write_bytes(b'elf')
        with patch.object(sys, 'platform', 'linux'), patch.object(
                desktop, 'player_program', lambda: str(player / 'horizon-play')), patch.object(
                desktop, 'release_assets', side_effect=AssertionError('no download needed')):
            self.assertEqual(self.get('linux'), str(player))
            (self.dir / 'd.bin').write_bytes(b'\x02' * 1000)
            (self.dir / 'd.cue').write_text('FILE "d.bin" BINARY\n  TRACK 01 MODE2/2352\n')
            out = desktop.make('linux', str(self.dir / 'd.cue'), 'v9.9.9')
            self.assertEqual(Path(out).name, 'd-Linux.run')

    def test_make_builds_next_to_the_disc(self):
        (self.dir / 'my disc.bin').write_bytes(b'\x01' * 4000)
        (self.dir / 'my disc.cue').write_text('FILE "my disc.bin" BINARY\n  TRACK 01 MODE2/2352\n')
        with patch.object(desktop, 'release_assets', lambda tag: self.assets()), patch.object(
                desktop, 'download', self.download):
            out = desktop.make('setup', str(self.dir / 'my disc.cue'), 'v9.9.9')
            self.assertEqual(Path(out).name, 'my disc-Setup.exe')
            self.assertTrue(setup_exe.read_trailer(out))
            self.remote['Horizon-Setup.exe'] = b'MZ'
            (self.dir / 'my disc.cue').write_text('REM none\n')
            with self.assertRaises(desktop.Problem) as e:
                desktop.make('setup', str(self.dir / 'my disc.cue'), 'v9.9.9')
            self.assertEqual(e.exception.key, 'app.makeFailed')


class MacApp(unittest.TestCase):
    """The Mac app with the player's disc inside (tools/patcher/mac_app.py)."""

    def make(self, d):
        d = Path(d)
        app = d / 'Horizon Play.app'
        (app / 'Contents' / 'MacOS').mkdir(parents=True)
        (app / 'Contents' / 'Resources').mkdir()
        (app / 'Contents' / 'MacOS' / 'horizon-play').write_bytes(b'#!exec')
        os.chmod(app / 'Contents' / 'MacOS' / 'horizon-play', 0o755)
        (app / 'Contents' / 'Resources' / 'core.dylib').write_bytes(b'core')
        os.symlink('core.dylib', app / 'Contents' / 'Resources' / 'link.dylib')
        (app / 'Contents' / 'Info.plist').write_bytes(plistlib.dumps(
            {'CFBundleName': 'Horizon Play', 'CFBundleIdentifier': 'com.dw1horizon.play'}))
        (d / 'my disc.bin').write_bytes(b'\x07\x08' * 20000)
        (d / 'my disc.cue').write_text('FILE "my disc.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        return d, app

    def test_app_gets_the_disc_and_the_name(self):
        with tempfile.TemporaryDirectory() as d:
            d, app = self.make(d)
            out = d / 'out.app'
            mac_app.build(str(app), str(d / 'my disc.cue'), str(out))
            res = out / 'Contents' / 'Resources'
            self.assertEqual((res / 'Digimon World Horizon.bin').read_bytes(), (d / 'my disc.bin').read_bytes())
            self.assertIn('FILE "Digimon World Horizon.bin"', (res / 'Digimon World Horizon.cue').read_text())
            plist = plistlib.loads((out / 'Contents' / 'Info.plist').read_bytes())
            self.assertEqual((plist['CFBundleName'], plist['CFBundleDisplayName'], plist['CFBundleIdentifier']),
                             ('Digimon World Horizon', 'Digimon World Horizon', 'com.dw1horizon.play'))
            self.assertTrue(os.path.islink(res / 'link.dylib'))
            self.assertTrue(os.access(out / 'Contents' / 'MacOS' / 'horizon-play', os.X_OK))

    def test_zip_keeps_symlinks_and_exec_bits(self):
        with tempfile.TemporaryDirectory() as d:
            d, app = self.make(d)
            seen = []
            mac_app.build(str(app), str(d / 'my disc.cue'), str(d / 'o.zip'), lambda a, b: seen.append((a, b)))
            self.assertEqual(seen[-1][0], seen[-1][1])
            with zipfile.ZipFile(d / 'o.zip') as z:
                modes = {i.filename: i.external_attr >> 16 for i in z.infolist()}
                base = 'Digimon World Horizon.app/Contents/'
                self.assertTrue(stat.S_ISLNK(modes[base + 'Resources/link.dylib']))
                self.assertEqual(z.read(base + 'Resources/link.dylib'), b'core.dylib')
                self.assertTrue(modes[base + 'MacOS/horizon-play'] & 0o100)
                self.assertEqual(z.read(base + 'Resources/Digimon World Horizon.bin'), (d / 'my disc.bin').read_bytes())
            self.assertEqual([p.name for p in d.iterdir() if p.name.startswith('.hzmac')], [])

    def test_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            d, app = self.make(d)
            with self.assertRaisesRegex(mac_app.MacAppError, 'Info.plist'):
                mac_app.build(str(d), str(d / 'my disc.cue'), str(d / 'o.zip'))
            with self.assertRaisesRegex(mac_app.MacAppError, 'must end'):
                mac_app.build(str(app), str(d / 'my disc.cue'), str(d / 'o.tar'))
            (d / 'my disc.bin').unlink()
            with self.assertRaises(setup_exe.SetupError):
                mac_app.build(str(app), str(d / 'my disc.cue'), str(d / 'o.zip'))
            if sys.platform != 'darwin':
                with self.assertRaisesRegex(mac_app.MacAppError, 'only be made on a Mac'):
                    mac_app.build(str(app), str(d / 'my disc.cue'), str(d / 'o.dmg'))


class LinuxRun(unittest.TestCase):
    """The Linux self-extracting installer (tools/patcher/linux_run.py)."""

    def make(self, d, as_tarball):
        d = Path(d)
        player = d / 'Horizon Play'
        (player / 'system').mkdir(parents=True)
        (player / 'horizon-play').write_text('#!/bin/sh\n')
        os.chmod(player / 'horizon-play', 0o755)
        (player / 'system' / 'openbios.bin').write_bytes(b'bios')
        if as_tarball:
            with tarfile.open(d / 'player.tar.gz', 'w:gz') as t:
                t.add(player, 'Horizon Play')
        (d / 'my disc.bin').write_bytes(bytes(range(256)) * 300)
        (d / 'my disc.cue').write_text('FILE "my disc.bin" BINARY\n  TRACK 01 MODE2/2352\n')
        return d, str(d / 'player.tar.gz') if as_tarball else str(player)

    @unittest.skipIf(os.name == 'nt', 'a POSIX sh script')
    def test_round_trip_install_and_uninstall(self):
        for as_tarball in (True, False):
            with self.subTest(tarball=as_tarball), tempfile.TemporaryDirectory() as d:
                d, player = self.make(d, as_tarball)
                out = str(d / 'disc-Linux.run')
                seen = []
                linux_run.build(player, str(d / 'my disc.cue'), out, lambda a, b: seen.append((a, b)))
                self.assertEqual(seen[-1][0], seen[-1][1])
                self.assertTrue(os.access(out, os.X_OK))
                env = dict(os.environ, HOME=str(d / 'home'), XDG_DATA_HOME=str(d / 'data'))
                inst = d / 'game dir'
                run = lambda *a: subprocess.run([out, *a], env=env, capture_output=True, text=True)
                r = run('--target', str(inst), '--no-start')
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual((inst / 'Digimon World Horizon.bin').read_bytes(), (d / 'my disc.bin').read_bytes())
                self.assertIn('FILE "Digimon World Horizon.bin"', (inst / 'Digimon World Horizon.cue').read_text())
                self.assertTrue(os.access(inst / 'horizon-play', os.X_OK))
                self.assertTrue((inst / 'system' / 'openbios.bin').is_file())
                self.assertTrue((inst / 'icon.png').read_bytes().startswith(b'\x89PNG'))
                launcher = (d / 'data' / 'applications' / 'digimon-world-horizon.desktop').read_text()
                self.assertIn(f'Exec="{inst}/horizon-play" "{inst}/Digimon World Horizon.cue"', launcher)
                (inst / 'keep.txt').write_text('not ours')   # a folder shared with other files stays
                self.assertEqual(run('--target', str(inst), '--uninstall').returncode, 0)
                self.assertEqual([p.name for p in inst.iterdir()], ['keep.txt'])
                self.assertFalse((d / 'data' / 'applications' / 'digimon-world-horizon.desktop').exists())

    def test_refuses_a_bundle_without_the_player(self):
        with tempfile.TemporaryDirectory() as d:
            d, player = self.make(d, False)
            os.remove(Path(player) / 'horizon-play')
            with self.assertRaisesRegex(linux_run.LinuxRunError, 'no horizon-play'):
                linux_run.build(player, str(d / 'my disc.cue'), str(d / 'o.run'))
            self.assertFalse((d / 'o.run').exists())
            with self.assertRaisesRegex(linux_run.LinuxRunError, 'no Linux'):
                linux_run.build(str(d / 'missing.tar.gz'), str(d / 'my disc.cue'), str(d / 'o.run'))


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
