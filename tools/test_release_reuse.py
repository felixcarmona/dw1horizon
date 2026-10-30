"""Tiny actual ISO/DWP fixtures: no game builds, source discs or emulators."""
import copy
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import release
import release_reuse as R

LAYOUT = '''<iso_project><track type="data" xa_edc="false">
<identifiers creation_date="2026102900000000"/><directory_tree>
<file name="SLUS_010.32" date="2026102900000000"/><file name="KEEP.DAT" date="2026102900000000"/><file name="SYSTEM.CNF" date="2026102900000000"/>
</directory_tree></track></iso_project>'''


class ReuseTests(unittest.TestCase):
    def files(self, exe):
        return {R.EXE: exe, 'KEEP.DAT': b'untouched', 'SYSTEM.CNF': b'BOOT = cdrom:\\SLUS_010.32;1\r\n'}

    def fixture(self, root, offset=2040):
        # The 32-byte buffer straddles two raw CD sectors, exercising both ECCs.
        old = bytes((k * 17) % 256 for k in range(5000))
        target = old[:offset] + R.version_bytes('0.0.0-dev.2+12345678') + old[offset + 32:]
        originals, entries = {}, {}
        blob = bytearray()
        for i, key in enumerate(sorted(R.BASES)):
            src = bytes((v + i) & 255 for v in old)
            path = root / (key + '.bin')
            R.iw.write(LAYOUT, self.files(src), str(path), cue=False, license=bytes(28032))
            originals[key] = R.iw.Image(str(path))
            # Deliberately mixed diff/extra/seek alignment, rather than a fixture
            # that assumes every byte of the delta is a simple subtraction.
            diff = bytes((a - b) & 255 for a, b in zip(target[:2050], src[:2050]))
            diff += bytes((a - b) & 255 for a, b in zip(target[2060:], src[2043:2043 + len(target) - 2060]))
            extra = target[2050:2060]
            entries[key] = dict(source=R.EXE, source_sha1=R.digest(src),
                control=[[2050, 10, -7], [len(target) - 2060, 0, 0]],
                diff=[len(blob), len(diff)], extra=[len(blob) + len(diff), len(extra)])
            blob.extend(diff + extra)
        payload = dict(layout=LAYOUT, sources=['SYSTEM.CNF'],
            files={R.EXE: [['b', 0, 0, len(target)]], 'KEEP.DAT': [['h', 0, 0, 9]], 'SYSTEM.CNF': [['s', 0]]},
            license=[['l', len(blob), 28032]], code=[],
            sha1={R.EXE: R.digest(target)},
            deltas=[dict(file=R.EXE, size=len(target), sha1=R.digest(target), bases=entries)],
            blob=bytes(blob) + originals['us'].license())
        return originals, payload, target

    def test_seven_base_restamp_matches_independent_images_and_payload_apply(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            originals, payload, target = self.fixture(root)
            self.addCleanup(lambda: [x.f.close() for x in originals.values()])
            offset, old, new = 2040, '0.0.0-dev.2+12345678', '0.0.1'
            # Build the untouched synthetic reference first using the full writer.
            source = root / 'reference.bin'
            R.iw.write(LAYOUT, self.files(target), str(source), cue=False, license=bytes(28032))
            unchanged = root / 'same.bin'
            R.restamp_image(source, unchanged, offset, old, old)
            self.assertEqual(release.sha1(source), release.sha1(unchanged))
            R.restamp_payload(payload, originals, offset, old, new)
            R.save_payload(root / 'new.dwp', payload)
            payload = R.dw.read_payload3((root / 'new.dwp').read_bytes())
            stamped = root / 'stamped.bin'
            proof = R.restamp_image(source, stamped, offset, old, new)
            self.assertEqual(set(k for k in proof['before'] if proof['before'][k] != proof['after'][k]), {R.EXE})
            expected = R.stamp(target, offset, old, new)
            independent = root / 'independent.bin'
            R.iw.write(LAYOUT, self.files(expected), str(independent), cue=False, license=bytes(28032))
            self.assertEqual(stamped.read_bytes(), independent.read_bytes())
            for key, image in originals.items():
                base = SimpleNamespace(key=key, map=None, code=image.read, data=image.read, source=image.source)
                output = root / ('applied-' + key + '.bin')
                R.dw.build_disc3(payload, base, {0: b'untouched'}, str(output), progress=False)
                self.assertEqual(output.read_bytes(), independent.read_bytes(), key)
            package = root / 'writer-package'
            package.mkdir()
            R.save_payload(package / 'everything.dwp', payload)
            images = root / 'outputs'
            images.mkdir()
            for key in originals:
                shutil.copyfile(independent, images / f'everything-{key}.bin')
            R.write(package / 'manifest.json', dict(variants={'everything': dict(
                patch='everything.dwp', patch_size=(package / 'everything.dwp').stat().st_size,
                patch_sha1=release.sha1(package / 'everything.dwp'),
                holes=[dict(id=0, file='KEEP.DAT', size=9, sha1=R.digest(b'untouched'))],
                outputs={key: {'sha1': release.sha1(independent)} for key in originals})},
                bases={key: {} for key in originals}))
            R.verify_outputs(package, images, {key: Path(image.path) for key, image in originals.items()}, {})
            tampered = R.read(package / 'manifest.json')
            tampered['variants']['everything']['outputs']['us']['sha1'] = 'bad'
            R.write(package / 'manifest.json', tampered)
            with self.assertRaisesRegex(RuntimeError, 'streamed package output'):
                R.verify_outputs(package, images, {key: Path(image.path) for key, image in originals.items()}, {})
            # Retain compact reviewable evidence in the test output.
            print(json.dumps(dict(reference=release.sha1(source), restamped=release.sha1(stamped),
                                  independently_written=release.sha1(independent), bases=len(originals))))

    @unittest.skipUnless(sys.version_info[:2] == (3, 10), 'actual isolated gate is Python 3.10 only')
    def test_cached_standalone_runner_with_shipped_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            originals, payload, target = self.fixture(root)
            self.addCleanup(lambda: [x.f.close() for x in originals.values()])
            package = root / 'package'
            package.mkdir()
            R.dw.copy_release_frontend(str(package))
            R.save_payload(package / 'everything.dwp', payload)
            retained = root / 'retained.bin'
            R.iw.write(LAYOUT, self.files(target), str(retained), cue=False, license=bytes(28032))
            original = Path(originals['us'].path)
            R.write(package / 'manifest.json', dict(default='everything',
                bases={'us': dict(title='Tiny USA', boot=R.EXE, size=original.stat().st_size,
                                  sha1=release.sha1(original))},
                variants={'everything': dict(patch='everything.dwp', patch_size=(package / 'everything.dwp').stat().st_size,
                    patch_sha1=release.sha1(package / 'everything.dwp'),
                    outputs={'us': {'sha1': release.sha1(retained)}},
                    holes=[dict(id=0, file='KEEP.DAT', size=9, sha1=R.digest(b'untouched'))])}))
            runner = root / 'runner.py'
            shutil.copyfile(R.ROOT / 'tools/release_cached_apply.py', runner)
            output = root / 'output.bin'
            subprocess.run([sys.executable, '-B', '-I', '-S', str(runner), str(package),
                            str(original), str(retained), str(output)], cwd=root, check=True,
                           stdout=subprocess.DEVNULL)
            self.assertEqual(output.read_bytes(), retained.read_bytes())

    def test_wrong_stamp_symbol_source_or_shared_version_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'buffer'):
            R.stamp(bytes(100), 5, '0.0.1', '0.0.2')
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            R.stamp(bytes(100), 99, '0.0.1', '0.0.2')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            originals, payload, target = self.fixture(root)
            self.addCleanup(lambda: [x.f.close() for x in originals.values()])
            bad = copy.deepcopy(payload)
            bad['deltas'][0]['bases']['us']['source_sha1'] = 'bad'
            with self.assertRaises(R.dw.PatchError):
                R.restamp_payload(bad, originals, 2040, '0.0.0-dev.2+12345678', '0.0.1')
            payload['files']['OTHER'] = [['o', R.EXE, 2040, 32]]
            with self.assertRaisesRegex(RuntimeError, 'reused'):
                R.restamp_payload(payload, originals, 2040, '0.0.0-dev.2+12345678', '0.0.1')
            path = root / 'map'
            for text in ('no symbol', '0x80091000 MOD_VERSION_TEXT\n0x80092000 MOD_VERSION_TEXT\n'):
                path.write_text(text)
                with self.assertRaisesRegex(RuntimeError, 'exactly one'):
                    R.version_offset(path)

    def test_engine_repack_preserves_graph_and_binds_embedded_package(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('engine_builder', R.ROOT / 'web/enginebuild/build_engine.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = root / 'package'
            package.mkdir()
            manifest = dict(default='everything', version='0.0.1', date='2026-10-29', commit='head',
                variants={'everything': {'patch': 'everything.dwp', 'outputs': {'us': {'sha1': 'expected'}}}})
            R.write(package / 'manifest.json', manifest)
            for name in ('everything.dwp', 'dwpatch.py', 'isowriter.py'):
                (package / name).write_bytes(b'initial')
            engine = root / 'engine'
            stage = engine / 'old'
            stage.mkdir(parents=True)
            files = {'.release/' + p.name: str(p) for p in package.iterdir()}
            other = root / 'other'
            other.write_bytes(b'graph code')
            files['tools/' + 'other.py'] = str(other)
            index, packs = builder.make_packs(str(root), files, set(files), str(stage))
            plan = dict(files=index, packs=packs, jobs=[{'id': 'unchanged'}],
                        release=dict(outputs=manifest['variants']['everything']['outputs']))
            R.write(stage / 'plan.json', plan)
            R.write(engine / 'current.json', {'version': 'old'})
            R.engine_package(engine, package)
            (package / 'everything.dwp').write_bytes(b'restamped deltas, changed length')
            with self.assertRaisesRegex(RuntimeError, 'engine package'):
                R.engine_package(engine, package)
            dest = root / 'repacked'
            R.repack_engine(engine, dest, package)
            stage, actual = R.engine_package(dest, package)
            self.assertEqual(plan['jobs'], actual['jobs'])
            row = next(row for row in actual['files'] if row[0] == 'tools/' + 'other.py')
            self.assertEqual(R.unpack_engine_file(stage, actual, row), b'graph code')

    def test_source_tree_or_artifact_mismatch_stops_before_commands(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            R.write(root / 'reuse.json', {'schema': 1, 'tree': 'old'})
            args = SimpleNamespace(reuse_from=root, skip_browser=False, record_save=None, save_check_emu=False)
            run = release.Run(False, root / 'out')
            with patch.object(release, 'git', return_value='new'), patch.object(run, 'cmd') as cmd:
                with self.assertRaisesRegex(RuntimeError, 'source tree'):
                    R.reuse(args, run, {})
                cmd.assert_not_called()
            source = root / 'package'
            source.mkdir()
            file = source / 'manifest.json'
            file.write_text('original')
            sums = R.inventory(source)
            file.write_text('tampered')
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                R.require_equal(R.inventory(source), sums, 'package')
            file.unlink()
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                R.require_equal(R.inventory(source), sums, 'missing package')
            file.symlink_to(root / 'reuse.json')
            with self.assertRaisesRegex(RuntimeError, 'symlinks'):
                R.inventory(source)


if __name__ == '__main__':
    unittest.main()
