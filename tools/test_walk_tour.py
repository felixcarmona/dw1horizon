#!/usr/bin/env python3
"""Tour failures must stop automation instead of silently skipping failed warps."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import sys
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.dev.walk import tour as tour


class TourTests(unittest.TestCase):
    def run_route(self, current, result=True):
        seg = Mock()
        seg.wp.return_value = (0, 0)
        seg.path.return_value = [(0, 0)]
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(tour, 'screen', return_value=current), \
                patch.object(tour.time, 'time', side_effect=range(1000)), \
                patch.object(tour.time, 'sleep'), \
                patch.object(tour, 'freeze_clock'), \
                patch.object(tour, 'pos', return_value=(0, 0)), \
                patch.object(tour, 'Seg', return_value=seg) as load, \
                patch.object(tour, 'go', return_value=result):
            tour.walk_tour([[300, 'unused.MAP', [[[1, 2], 0]]]], str(Path(tmp) / 'log.json'))
            return load.call_count

    def test_missing_screen_is_a_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'expected screen 300, still on 299'):
            self.run_route(299)

    def test_unreachable_waypoint_is_a_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'could not reach waypoint'):
            self.run_route(300, False)

    def test_arrived_waypoint_succeeds(self):
        self.assertEqual(self.run_route(300), 1)

    def test_warp_leaves_segment_normally(self):
        self.assertEqual(self.run_route(300, 'left'), 1)


class WalkScriptTests(unittest.TestCase):
    def test_batch_wrapper_preserves_tour_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tools/dev/walk').mkdir(parents=True)
            script = Path(__file__).resolve().parent / 'dev/walk/walkall.sh'
            shutil.copy(script, root / 'tools/dev/walk/walkall.sh')
            bindir = root / 'bin'
            bindir.mkdir()
            for name, body in {
                'bin/sleep': 'exit 0',
                'tools/dev/emulator.py': 'exit 0',
                'tools/dev/game_state.py': 'echo "tamer.state 0"; echo "game_state 0"; echo "script_paused 1"; echo "current_screen 300"',
                'tools/dev/walk/walk.sh': 'echo "failed tour"; exit 7',
            }.items():
                f = root / name
                f.write_text('#!/bin/sh\n' + body + '\n')
                f.chmod(0o755)
            env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                       WALKS='test:tour.json:300:0:20', SEND='0')
            run = subprocess.run(['bash', 'tools/dev/walk/walkall.sh'], cwd=root, env=env,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 7, run.stdout + run.stderr)

    def test_recording_wrapper_preserves_tour_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tools/dev/walk').mkdir(parents=True)
            script = Path(__file__).resolve().parent / 'dev/walk/walk.sh'
            shutil.copy(script, root / 'tools/dev/walk/walk.sh')
            bindir = root / 'bin'
            bindir.mkdir()
            stubs = {
                'sleep': 'exit 0',
                'timeout': 'exit 7',
                'python3': 'exit 0',
                'cp': 'exit 0',
            }
            for name, body in stubs.items():
                f = bindir / name
                f.write_text('#!/bin/sh\n' + body + '\n')
                f.chmod(0o755)
            for name, body in {
                'emulator.py': 'exit 0',
                'game_state.py': 'echo "tamer.state 0"; echo "game_state 0"',
            }.items():
                f = root / 'tools/dev' / name
                f.write_text('#!/bin/sh\n' + body + '\n')
                f.chmod(0o755)
            env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'], PY='/bin/true')
            run = subprocess.run(['bash', 'tools/dev/walk/walk.sh', 'test', 'tour.json', '300', '0', '20'],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 7, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
