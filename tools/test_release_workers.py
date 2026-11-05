"""Release scheduling and content-verified cache checks without player discs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_workers as workers
from tools.derive import release_cache as cache
from tools import build_cache


class Workers(unittest.TestCase):
    def test_parallel_bytes_equal_sequential_with_ordered_merge(self):
        active, peak = 0, 0
        lock = threading.Lock()

        def make(i):
            def work():
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep((8-i) * .002)
                data = hashlib.sha256(str(i).encode()).digest() * 100
                with lock:
                    active -= 1
                return data
            return work

        tasks = {str(i): make(i) for i in range(8)}
        sequential = workers.ordered(tasks, 1)
        parallel = workers.ordered(tasks, 4)
        self.assertEqual(list(sequential), list(parallel))
        self.assertEqual(b''.join(sequential.values()), b''.join(parallel.values()))
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)

    def test_error_requests_cancellation(self):
        stopped = threading.Event()
        def failure():
            raise RuntimeError('gate failed')
        with self.assertRaisesRegex(RuntimeError, 'gate failed'):
            workers.ordered({'failure': failure, 'running': lambda: stopped.wait(1)}, 2, stopped.set)
        self.assertTrue(stopped.is_set())

    def test_memory_cpu_and_task_limits(self):
        with patch.object(Path, 'read_text', return_value='MemAvailable: 20971520 kB\n'), \
                patch.object(os, 'cpu_count', return_value=16):
            self.assertEqual(workers.worker_count(7, 8, 6144), 2)
            self.assertEqual(workers.worker_count(1, 8), 1)
            self.assertEqual(workers.worker_count(7, 1), 1)
            with self.assertRaises(ValueError):
                workers.worker_count(0, 7)

    @unittest.skipUnless(Path('/proc/self/stat').exists(), 'Linux RSS sampler')
    def test_rss_includes_live_worker(self):
        reports = []
        with workers.measure(os.getpid(), reports.append):
            time.sleep(.05)
        self.assertGreater(reports[0]['peak_rss_kib'], 0)


class RecordingCache(unittest.TestCase):
    def test_player_replay_does_not_enter_release_helpers(self):
        import shutil
        import subprocess
        import dwpatch as dw
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copyfile(dw.__file__, root / 'dwpatch.py')
            bundle = root / 'bundle'
            recipe = bundle / 'tools/derive/recipes/everything.json'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(json.dumps({'environment': {'NAME': 'everything'}}))
            (bundle / 'tools/__init__.py').write_text('')
            (bundle / 'tools/derive/__init__.py').write_text('')
            (bundle / 'exe-facts.json').write_text('{}')
            (bundle / 'tools/derive/__main__.py').write_text(
                "import json,os,pathlib\n"
                "assert not any(k in os.environ for k in ('DW_BUILD_CACHE','DW_RECORD_CACHE'))\n"
                "out=pathlib.Path('build/everything'); (out/'derived').mkdir(parents=True)\n"
                "(out/'model').write_bytes(b'player bytes')\n"
                "(out/'derived/manifest.json').write_text(json.dumps({'files':{'MODEL':{'file':'model'}}}))\n")
            script = (
                "import pathlib,sys; from types import SimpleNamespace; "
                "sys.path.insert(0,sys.argv[1]); import dwpatch as dw; root=pathlib.Path(sys.argv[1]); "
                "got=dw.derive_holes(str(root),{'extract':[]},{'local':{'recipe':'everything'}},"
                "SimpleNamespace(data=lambda _:b''),str(root/'work')); "
                "assert pathlib.Path(got['MODEL']).read_bytes()==b'player bytes'")
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
            env.update(DW_BUILD_CACHE='must-not-be-used', DW_RECORD_CACHE='must-not-be-used')
            result = subprocess.run([sys.executable, '-I', '-B', '-E', '-S', '-c', script, td], cwd=td,
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_launcher_metadata_does_not_prevent_cross_release_hits(self):
        import dwpatch as dw
        first = {'SPECIES': 'all', 'FUTURE_BUILD_FLAG': 'one', 'CODEX_THREAD_ID': 'first',
                 'CLAUDE_CODE_SESSION_ID': 'first', 'NAME': 'release-first', 'W': '/first'}
        second = dict(first, CODEX_THREAD_ID='second', CLAUDE_CODE_SESSION_ID='second',
                      NAME='release-second', W='/second')
        self.assertEqual(dw.release_cache_environment(first), dw.release_cache_environment(second))
        second['FUTURE_BUILD_FLAG'] = 'two'
        self.assertNotEqual(dw.release_cache_environment(first), dw.release_cache_environment(second))

    def test_fingerprint_tracks_all_inputs_and_ignores_location(self):
        with tempfile.TemporaryDirectory() as td, \
                patch('tools.derive.cache.runtime_sources', return_value='runtime'):
            root = Path(td) / 'input'; root.mkdir()
            source = Path(td) / 'disc'; source.write_bytes(b'original')
            file = root / 'recipe.py'; file.write_text('code')
            def fingerprint():
                return cache.fingerprint(root, 'everything', ['dw2003=' + str(source)], {'TEXT': 'ours'})
            first = fingerprint()
            other = Path(td) / 'relocated'
            __import__('shutil').copytree(root, other)
            self.assertEqual(first, cache.fingerprint(other, 'everything', ['dw2003=' + str(source)], {'TEXT': 'ours'}))
            for change in (lambda: file.write_text('new code'), lambda: source.write_bytes(b'new source'),
                           lambda: (root / 'formerly-absent').write_text('new input')):
                before = fingerprint(); change(); self.assertNotEqual(before, fingerprint())
            self.assertNotEqual(fingerprint(), cache.fingerprint(root, 'everything', ['dw2003=' + str(source)], {'TEXT': 'us'}))

    def test_snapshot_hashes_all_outputs_before_restoring(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'tree'; root.mkdir()
            (root / 'model').write_bytes(b'correct')
            (root / 'empty-output').mkdir()
            snapshot = Path(td) / 'snapshot'
            cache.save(snapshot, root)
            (root / 'model').unlink()
            (root / 'empty-output').rmdir()
            self.assertTrue(cache.restore(snapshot, root))
            self.assertEqual((root / 'model').read_bytes(), b'correct')
            self.assertTrue((root / 'empty-output').is_dir())
            (snapshot / 'tree/model').write_bytes(b'corrupt')
            self.assertFalse(cache.restore(snapshot, root))

    def test_real_recording_subprocess_reuses_only_identical_inputs(self):
        import contextlib
        import io
        import shutil
        import dwpatch as dw
        with tempfile.TemporaryDirectory() as td, \
                patch('tools.derive.cache.runtime_sources', return_value='runtime'):
            root = Path(td)
            supplied = root / 'supplied'
            recipe = supplied / 'tools/derive/recipes/everything.json'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(json.dumps({'environment': {'NAME': 'everything'}}))
            (supplied / 'exe-facts.json').write_text('first facts')
            (supplied / 'tools/derive/__main__.py').write_text(
                "import json,pathlib\n"
                "root=pathlib.Path.cwd(); out=root/'build/everything'\n"
                "(out/'derived').mkdir(parents=True)\n"
                "(out/'model').write_bytes((root/'exe-facts.json').read_bytes())\n"
                "(out/'derived/manifest.json').write_text(json.dumps({'files':{'MODEL':{'file':'model'}}}))\n")
            calls = []
            for n in range(3):
                if n == 2:
                    (supplied / 'exe-facts.json').write_text('changed facts')
                attempt = root / str(n)
                shutil.copytree(supplied, attempt)
                with patch.object(dw, 'derive_run', wraps=dw.derive_run) as run, \
                        contextlib.redirect_stdout(io.StringIO()):
                    man, out = dw.release_derive(str(attempt), 'everything', str(attempt / 'exe-facts.json'),
                                                cache=str(root / 'cache'), slot='recording', record=True)
                calls.append(run.call_count)
                self.assertEqual((Path(out) / 'model').read_bytes(), (supplied / 'exe-facts.json').read_bytes())
                self.assertEqual(man['files']['MODEL']['file'], 'model')
            self.assertEqual(calls, [1, 0, 1])

    def test_step_cache_rebuilds_only_changed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); build = root / 'build'; build.mkdir()
            a, b = root / 'a', root / 'b'
            a.write_bytes(b'A'); b.write_bytes(b'B')
            calls = []
            def compile_file(source, output):
                calls.append(source.name)
                output.write_bytes(source.read_bytes().upper())
                return {'ok': True}
            artifacts = build_cache.Cache(root / 'cache', build)
            for source in (a, b):
                artifacts.call({'name': source.name}, lambda s=source: compile_file(s, build / s.name))
            for p in build.iterdir():
                if p.is_file(): p.unlink()
            a.write_bytes(b'changed')
            hits = [artifacts.call({'name': s.name}, lambda s=s: compile_file(s, build / s.name))[1] for s in (a, b)]
            self.assertEqual(hits, [False, True])
            self.assertEqual(calls, ['a', 'b', 'a'])
            self.assertEqual((build / 'a').read_bytes(), b'CHANGED')
            self.assertEqual((build / 'b').read_bytes(), b'B')


class DeltaCache(unittest.TestCase):
    def test_hits_invalidation_and_corruption(self):
        import delta_cache
        import codecopy
        with tempfile.TemporaryDirectory() as td:
            old, new = bytes(range(256)), b'own' + bytes(range(256))
            first = delta_cache.delta(old, new, td)
            with patch.object(codecopy, 'make_delta', side_effect=AssertionError('cache miss')):
                self.assertEqual(first, delta_cache.delta(old, new, td))
            with patch.object(codecopy, 'make_delta', wraps=codecopy.make_delta) as make:
                delta_cache.delta(old, new + b'change', td)
                make.assert_called_once()
            for entry in Path(td).glob('*.json.z'):
                entry.write_bytes(b'corrupt')
            with patch.object(codecopy, 'make_delta', wraps=codecopy.make_delta) as make:
                self.assertEqual(first, delta_cache.delta(old, new, td))
                make.assert_called_once()


if __name__ == '__main__':
    unittest.main()
