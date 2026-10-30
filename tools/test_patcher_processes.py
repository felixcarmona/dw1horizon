"""Standalone derive must finish killing workers before apply removes their directory."""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import dwpatch as dw


class Processes(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'real POSIX process groups')
    def test_interrupt_and_failure_kill_descendants_even_after_parent_exits(self):
        real_popen = subprocess.Popen
        for mode in ('interrupt', 'failure', 'inherited-pipe-failure', 'read-error'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                recipe = root / 'tools/derive/recipes'
                recipe.mkdir(parents=True)
                (recipe / 'fixture.json').write_text(json.dumps({'environment': {'NAME': 'fixture'}}))
                pidfile = root / 'child.pid'
                child_code = ('import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                              'print("ready",flush=True); time.sleep(60)')
                code = ('import subprocess,sys,time,pathlib; '
                        f'p=subprocess.Popen([sys.executable,"-c",{child_code!r}],stdout=subprocess.PIPE,'
                        + ('stderr=None); ' if mode == 'inherited-pipe-failure' else 'stderr=subprocess.DEVNULL); ')
                        + 'p.stdout.readline(); '
                        f'pathlib.Path({str(pidfile)!r}).write_text(str(p.pid)); '
                        'print("ready",flush=True); '
                        + ('sys.exit(2)' if mode in ('failure', 'inherited-pipe-failure') else 'time.sleep(60)'))
                parent = None
                def launch(argv, **kwargs):
                    nonlocal parent
                    # Isolate even the old implementation so a failed regression can clean its fixture.
                    kwargs.setdefault('start_new_session', True)
                    parent = real_popen([sys.executable, '-c', code], **kwargs)
                    if mode not in ('failure', 'inherited-pipe-failure'):
                        parent.stdout.readline()
                        stream = parent.stdout
                        class BrokenRead:
                            def __iter__(self): return self
                            def __next__(self):
                                if mode == 'interrupt': raise KeyboardInterrupt
                                raise OSError('read failed')
                            def close(self): stream.close()
                        parent.stdout = BrokenRead()
                    return parent
                try:
                    with patch.object(dw.subprocess, 'Popen', side_effect=launch):
                        error = dw.PatchError if mode in ('failure', 'inherited-pipe-failure') else KeyboardInterrupt if mode == 'interrupt' else OSError
                        with self.assertRaises(error): dw.derive_run(td, 'fixture', 'unused', log=str(root/'log'))
                    self.assertIsNotNone(parent.returncode)
                    pid = int(pidfile.read_text())
                    # A killed orphan may remain a zombie until the host init reaps it.
                    stat = Path(f'/proc/{pid}/stat')
                    for _ in range(100):
                        if not stat.exists() or stat.read_text().split()[2] == 'Z': break
                        time.sleep(.01)
                    if stat.exists(): self.assertEqual(stat.read_text().split()[2], 'Z')
                finally:
                    if parent and parent.poll() is None: os.killpg(parent.pid, signal.SIGKILL); parent.wait()
                    if pidfile.exists():
                        try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
                        except ProcessLookupError: pass

    @unittest.skipUnless(sys.platform.startswith('linux'), 'real Linux Ctrl-C')
    def test_real_ctrl_c_stops_the_detached_derive_group(self):
        patcher = str(Path(dw.__file__).resolve().parent)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); recipe = root/'tools/derive/recipes'; recipe.mkdir(parents=True)
            for package in ('tools', 'tools/derive'):
                (root/package/'__init__.py').write_text('')
            (recipe/'fixture.json').write_text('{"environment":{"NAME":"fixture"}}')
            marker = root/'pids.json'
            fixture = ('import os,subprocess,sys,time,json\n'
                       'child=subprocess.Popen([sys.executable,"-c",'
                       '\'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)\'])\n'
                       f'open({str(marker)!r},"w").write(json.dumps([os.getpid(),child.pid]))\n'
                       'print("ready",flush=True)\ntime.sleep(60)\n')
            (root/'tools/derive/__main__.py').write_text(fixture)
            code = f'import sys;sys.path.insert(0,{patcher!r});import dwpatch;dwpatch.derive_run({td!r},"fixture","unused")'
            apply = subprocess.Popen([sys.executable, '-c', code], start_new_session=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pids = []
            try:
                for _ in range(200):
                    if marker.exists():
                        try: pids = json.loads(marker.read_text()); break
                        except ValueError: pass
                    if apply.poll() is not None: break
                    time.sleep(.01)
                self.assertEqual(len(pids), 2, apply.poll())
                # Allow the child to install its SIGTERM handler before interrupting apply.
                time.sleep(.1)
                os.kill(apply.pid, signal.SIGINT)
                stdout, stderr = apply.communicate(timeout=6)
                self.assertNotEqual(apply.returncode, 0)
                self.assertIn(b'KeyboardInterrupt', stderr)
                for pid in pids:
                    stat = Path(f'/proc/{pid}/stat')
                    for _ in range(100):
                        if not stat.exists() or stat.read_text().split()[2] == 'Z': break
                        time.sleep(.01)
                    if stat.exists(): self.assertEqual(stat.read_text().split()[2], 'Z')
            finally:
                for pid in pids:
                    try: os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                if apply.poll() is None: os.killpg(apply.pid, signal.SIGKILL)
                apply.communicate()

    def test_windows_job_owns_parent_before_derive_is_allowed_to_run(self):
        events = []; captured = []
        class Pipe(io.BytesIO):
            def write(self, data): events.append('release'); return super().write(data)
        class Process:
            stdin = Pipe()
            stdout = io.BytesIO()
            def wait(self): events.append('wait'); return 2
            def poll(self): return 2
        class Job:
            def __init__(self): events.append('job')
            def assign(self, process): events.append('assign')
            def close(self): events.append('close-job')
        def launch(argv, **kw):
            captured.append(argv)
            events.append('launch')
            self.assertEqual(kw['creationflags'], 512)
            self.assertEqual(kw['stdin'], subprocess.PIPE)
            self.assertIn('sys.stdin.buffer.read(1)', argv[2])
            self.assertEqual(argv[3:6], ['tools.derive', 'build', '--recipe'])
            return Process()
        with tempfile.TemporaryDirectory() as td:
            recipe = Path(td)/'tools/derive/recipes'; recipe.mkdir(parents=True)
            (recipe/'fixture.json').write_text('{"environment":{"NAME":"fixture"}}')
            with patch.object(dw.os, 'name', 'nt'), patch.object(dw, '_WindowsDeriveJob', Job), \
                 patch.object(dw.subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, create=True), \
                 patch.object(dw.subprocess, 'Popen', side_effect=launch):
                with self.assertRaises(dw.PatchError): dw.derive_run(td, 'fixture', 'unused')
        self.assertEqual(events[:4], ['job', 'launch', 'assign', 'release'])
        self.assertLess(events.index('close-job'), len(events)-1)
        # The gate itself is platform-independent Python: EOF after apply dies
        # before job assignment must exit, rather than start an unowned derive.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'tools/derive').mkdir(parents=True)
            for package in ('tools', 'tools/derive'):
                (root/package/'__init__.py').write_text('')
            (root/'tools/derive/__main__.py').write_text('print("derive started")')
            for token in (b'', b'x', b'1'):
                result = subprocess.run(captured[0], cwd=td, input=token, capture_output=True)
                self.assertEqual(result.returncode, 0 if token == b'1' else 1)
                self.assertEqual(result.stdout, b'derive started\n' if token == b'1' else b'')

    def test_windows_assignment_failure_never_releases_the_gated_process(self):
        events = []
        class Pipe(io.BytesIO):
            def write(self, data): raise AssertionError('derive ran without a job')
        class Process:
            stdin = Pipe(); stdout = io.BytesIO()
            def kill(self): events.append('kill')
            def wait(self): events.append('wait'); return -1
            def poll(self): return None
        class Job:
            def assign(self, process): raise OSError('job assignment failed')
            def close(self): events.append('close-job')
        with tempfile.TemporaryDirectory() as td:
            recipe = Path(td)/'tools/derive/recipes'; recipe.mkdir(parents=True)
            (recipe/'fixture.json').write_text('{"environment":{"NAME":"fixture"}}')
            with patch.object(dw.os, 'name', 'nt'), patch.object(dw, '_WindowsDeriveJob', Job), \
                 patch.object(dw.subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, create=True), \
                 patch.object(dw.subprocess, 'Popen', return_value=Process()):
                with self.assertRaisesRegex(OSError, 'job assignment failed'):
                    dw.derive_run(td, 'fixture', 'unused')
        self.assertEqual(events[:3], ['close-job', 'kill', 'wait'])


if __name__ == '__main__': unittest.main()
