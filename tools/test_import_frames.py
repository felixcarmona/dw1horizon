#!/usr/bin/env python3
"""Replay optimizations: deferred edits, exact matrices and repeated solver states.

Run: python3 tools/test_import_frames.py. Full model/disc pins are checked by
web/test/suite.sh; these cases cover state and signed-zero boundaries too.
"""
from collections import OrderedDict
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import mmd
import mmdport
import retarget
from tools.derive import crmath
from tools.derive.importers import Provider


class ReplayFrames(unittest.TestCase):
    def setUp(self):
        crmath.install()

    def tearDown(self):
        crmath.uninstall()
        crmath.clear()

    def test_deferred_edits_run_once_in_order(self):
        calls = []

        def read():
            calls.append('read')
            return [[2, 3]]

        a = mmdport.Anim(read, 30, True)
        a.map_frames(lambda f: [[x * 2 for x in row] for row in f])
        a.map_frames(lambda f: [row[::-1] for row in f])
        self.assertEqual(calls, [])
        self.assertEqual(a.frames, [[6, 4]])
        self.assertIs(a.frames, a.frames)
        self.assertEqual(calls, ['read'])
        self.assertEqual((a.fps, a.loop), (30, True))
        # Existing frames still receive in-place edits immediately, including
        # aliases used by DW2's concatenated animations.
        shared = a.frames[0]
        def edit(frames):
            frames[0][0] = 9
            return frames
        a.map_frames(edit)
        self.assertEqual(shared, [9, 4])

    def test_affine_chain_matches_independent_calculations(self):
        rng = random.Random(727)
        for _ in range(100):
            n = rng.randint(2, 34)
            skel = [(-1, -1)] + [(i - 1, rng.randrange(i)) for i in range(1, n)]
            pose = [[4096] * 3 + [rng.randint(-8000, 8000) for _ in range(3)] +
                    [rng.randint(-3000, 3000) for _ in range(3)] for _ in range(n)]
            rotations, positions = retarget.world_transform(skel, pose)
            self.assertEqual(rotations, retarget.world_rots(skel, pose))
            self.assertEqual(positions, retarget.world_pos(skel, pose))

    def test_repeat_search_respects_events_and_loop_boundary(self):
        # The 80-frame case uses the standard-library path; 240 frames uses
        # numpy when available. Root travel repeats by a constant offset.
        for n, repeats in ((80, 19), (240, 59)):
            samples = [[[i * 2, i % 4, 0, 0, 0, 0, 0, 0, 0]] for i in range(n)]
            self.assertEqual(mmd.find_repeats(samples), [(0, 4, repeats)])
            self.assertEqual(mmd.find_repeats(samples, before=39), [(0, 4, 9)])
            event = [(20, 'sound', dict(bank=4, note=5))]
            self.assertEqual(mmd.find_repeats(samples, event), [(0, 4, 5), (21, 4, repeats - 5)])

    def test_recorded_mesh_choice_falls_back_on_source_pin_mismatch(self):
        for fast_matches in (True, False):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'spec.json').write_bytes(b'{}')
                provider = object.__new__(Provider)
                provider.repo, provider.work = root, root / 'work'
                provider.cache, provider.sizes = {}, {}
                provider.source_pins = {'build/model/X.MMD': hashlib.sha256(b'correct').hexdigest()}
                provider.batches = {'build/model/X.MMD': dict(out='build/model', entry={'name': 'X'},
                    level=3, spec='spec.json', spec_sha256=hashlib.sha256(b'{}').hexdigest())}
                attempts = []
                def replay(entry, level, spec, out, log, frozen_mesh=True):
                    attempts.append(frozen_mesh)
                    out = Path(out)
                    out.mkdir(parents=True, exist_ok=True)
                    data = b'correct' if fast_matches or not frozen_mesh else b'old choice'
                    (out / 'X.MMD').write_bytes(data)
                    (out / 'X.TIM').write_bytes(b'texture')
                with patch.dict(sys.modules, {'import_batch': SimpleNamespace(replay_model=replay),
                                              'sizes': SimpleNamespace()}):
                    self.assertEqual(provider.source('build/model/X.MMD'), b'correct')
                self.assertEqual(attempts, [True] if fast_matches else [True, False])

    def test_recorded_mesh_choice_preserves_entry_budgets(self):
        import import_batch
        entry = dict(name='X', meshfix=dict(prims=600, hidden=False))
        spec = dict(name='X', meshfix=dict(kappa=3.0, kmove=3.0, quad_angle=40.0, prims=713))
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(import_batch, 'load_source', return_value=(None, {})) as read, \
                patch.object(import_batch, 'merge_palettes'), patch.object(import_batch, 'size_source'), \
                patch.object(mmdport, 'build_partner', return_value=b'model'):
            import_batch.replay_model(entry, 6, spec, directory)
            self.assertEqual(read.call_args.args[0]['meshfix'],
                             dict(prims=600, hidden=False, kappa=3.0, kmove=3.0, quad_angle=40.0))
            import_batch.replay_model(entry, 6, spec, directory, frozen_mesh=False)
            self.assertEqual(read.call_args.args[0], entry)
        self.assertEqual(entry['meshfix'], dict(prims=600, hidden=False))

    def test_retarget_cache_includes_layer_and_previous_solution(self):
        skel = [(-1, -1), (0, 0), (1, 1)]
        exe = SimpleNamespace(bone_count=[3, 3], skeleton=[skel, skel])
        src = SimpleNamespace(anims=SimpleNamespace(table=[0], anims=[None]))
        rest = [[4096] * 3 + [0] * 6 for _ in range(3)]
        samples = []
        for i in range(180):
            p = [v[:] for v in rest]
            p[0][6] = i * 7  # root travel must not be reused with a cached pose
            p[2][3:6] = [(i % 8) * 100, 200, -100]
            p[2][7] = i % 8
            samples.append(p)
        def layer(t):
            return {1: mmd.rot_matrix(0, (t % 3) * 128, 0)}
        class NoHits(OrderedDict):
            def __contains__(self, key):
                return False
        args = (src, 0, 0, 1, rest, {2: (2, 0.75)}, (2, 2, 0.5))
        with patch.object(mmd, 'exe', return_value=exe), \
                patch.object(retarget, 'play', return_value=(samples, None, [])):
            with patch.object(retarget, 'world_transform', wraps=retarget.world_transform) as work:
                cached = retarget.transfer(*args, layered=layer)
                cached_calls = work.call_count
            with patch.object(retarget, 'OrderedDict', NoHits), \
                    patch.object(retarget, 'world_transform', wraps=retarget.world_transform) as work:
                uncached = retarget.transfer(*args, layered=layer)
                self.assertLess(cached_calls, work.call_count / 2)
        self.assertEqual(json.dumps(cached), json.dumps(uncached))

    def test_dcb_rotation_preserves_bits_and_returns_fresh_arrays(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('numpy is needed for the source reader')
        spec = importlib.util.spec_from_file_location('dcb_pose_test',
                    ROOT / 'tools/derive/importers/vendor/dcb/pose.py')
        pose = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pose)
        rng = random.Random(232)
        angles = [(0., -0., 0.), (-0., 0., -0.)]
        angles += [tuple(rng.randrange(-8192, 8192) for _ in range(3)) for _ in range(100)]
        def multiply(a, b):
            return np.array([[sum(float(a[i, k]) * float(b[k, j]) for k in range(3))
                              for j in range(3)] for i in range(3)])
        for a in angles:
            x, y, z = np.asarray(a, float) * pose.ANGLE
            reference = multiply(multiply(pose.rot_y(y), pose.rot_x(x)), pose.rot_z(z))
            self.assertEqual(reference.tobytes(), pose.rotation(a).tobytes())
            pose.rotation(a)[:] = 99
            self.assertEqual(reference.tobytes(), pose.rotation(a).tobytes())


if __name__ == '__main__':
    unittest.main()
