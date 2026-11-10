"""Gizamon's hind legs in the walk, condition walk and run (field_animations/gizamon_hind.py): feet planted, knees
beside the shell and never wound round the hip, the mouth opening a little and shut at both ends of each clip, hip angles continuous and the hip turning
smoothly between ticks at 60 fps, thigh and shin not twisting round their length, the two hind feet half a cycle apart, nothing else changed.
Needs the delta model and the DW1 extraction:

    python3 tools/models/edit.py get 239      (writes build/imported-model-edit/edit/239-Gizamon.MMD)"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import numpy as np
import animsheet
import mmd
import motionstorage
from motiontailspace import interpolate_pose
from tools.models.field_animations import followthrough as F

SOURCE = Path(os.environ.get('GIZAMON_MODEL', 'build/imported-model-edit/edit/239-Gizamon.MMD'))
HIPS = {10: (11, 12), 13: (14, 15)}          # hip: (knee, ankle)
SLOTS = {2: (12, 20), 3: (18, 13.3333), 4: (8, 40)}


class GizamonHind(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the Gizamon delta model and the player DW1 extraction')
        cfg = json.loads(F.MANIFEST.read_text())['239']
        data = SOURCE.read_bytes()
        if hashlib.sha256(data).hexdigest() != cfg['source_sha256']:
            raise unittest.SkipTest('the model is not the one the overlay was authored from')
        cls.sk = cfg['skeleton']
        mmd.exe().add_type(239, cls.sk)

        def make(c):
            m = mmd.MMD.parse(data, len(cls.sk))
            m.type = 239
            out = F.amphibian(m, cls.sk, c)
            m = mmd.MMD.parse(out, len(cls.sk))
            m.type = 239
            return out, m

        old = copy.deepcopy(cfg)
        old.pop('hind')
        old.pop('mouth')
        shut = copy.deepcopy(cfg)
        shut.pop('mouth')
        cls.mouth = cfg['mouth']
        cls.out, cls.model = make(cfg)
        _, cls.old = make(old)
        _, cls.shut = make(shut)

    def clip(self, model, slot):
        return animsheet.slot_frames(model, len(self.sk), slot)[0]

    def worlds(self, model, slot):
        """Per tick: bone matrices of the root-free pose and the root z."""
        out = []
        for f in self.clip(model, slot):
            out.append((np.array(mmd.bone_matrices(model, [[4096] * 3 + [0] * 6] + [list(b) for b in f[1:]])), f[0][8]))
        return out

    def test_only_the_hind_legs_and_the_mouth_change(self):
        idle = self.mouth['idle']['repeats']
        for slot in range(64):
            try:
                new, old = self.clip(self.model, slot), self.clip(self.old, slot)
            except Exception:
                continue
            if slot in (0, 1):          # the idle bob played several times, the mouth aside
                self.assertEqual(len(new) - 1, idle * (len(old) - 1))
                for t, a in enumerate(new):
                    b = old[t % (len(old) - 1)]
                    self.assertEqual(a[:2] + a[4:], b[:2] + b[4:], (slot, t))
                continue
            if slot not in SLOTS:
                self.assertEqual(new, old, slot)
                continue
            self.assertEqual(len(new), len(old))
            for a, b in zip(new, old):
                self.assertEqual(a[:2] + a[4:10], b[:2] + b[4:10], slot)
        audit = motionstorage.audit(self.out, len(self.sk))
        self.assertTrue(audit['fits'])
        self.assertLessEqual(audit['resident_bytes'], 100352)

    def test_mouth_opens_a_little_and_is_shut_at_both_ends(self):
        # Opening = how far the jaw (bone 3, +x drops it) turns down against the head (bone 2) beyond the clip
        # without the mouth pass. 4096 units a turn: 200 is about 18 degrees.
        for slot, (lo, hi) in {0: (80, 200), 1: (80, 200), 2: (20, 120), 3: (20, 120), 4: (20, 120)}.items():
            new, shut = self.clip(self.model, slot), self.clip(self.shut, slot)
            if slot in (0, 1):        # the native idle bob, repeated
                shut = [shut[t % (len(shut) - 1)] for t in range(len(new))]
            self.assertEqual(len(new), len(shut), slot)
            self.assertEqual(new[0][1:], new[-1][1:], slot)    # seamless loop (the root moves on)
            opening = [a[3][3] - b[3][3] for a, b in zip(new, shut)]
            self.assertEqual(opening[0], 0, slot)              # shut where every clip hands over
            self.assertEqual(opening[-1], 0, slot)
            self.assertGreaterEqual(min(opening), 0, slot)
            self.assertTrue(lo <= max(opening) <= hi, (slot, max(opening)))
            for a, b in zip(new, shut):                       # only the head pitch and the jaw move
                self.assertEqual(a[:2] + a[4:], b[:2] + b[4:], slot)
                self.assertEqual(a[2][4:] + a[3][4:], b[2][4:] + b[3][4:], slot)
            steps = [abs(b - a) for a, b in zip(opening, opening[1:])]
            self.assertLess(max(steps), 40, slot)             # eased, no snap between two ticks
            rises = sum(1 for a, b, c in zip(opening, opening[1:], opening[2:]) if b > a and b >= c)
            self.assertEqual(rises, 1 if slot in (0, 1) else 2, slot)   # once per idle loop, once per step
            if slot in SLOTS:                                  # shut on each footfall (phase 0 and one half)
                self.assertEqual(opening[len(new) // 2], 0, slot)

    def test_clips_loop_and_keep_timing(self):
        for slot, (ticks, speed) in SLOTS.items():
            f = self.clip(self.model, slot)
            self.assertEqual(len(f) - 1, ticks)
            self.assertAlmostEqual(f[1][0][8] - f[0][0][8], -speed, delta=1)
            self.assertEqual(f[0][1:], f[-1][1:], slot)

    def test_feet_planted_and_half_a_cycle_apart(self):
        for slot, (ticks, speed) in SLOTS.items():
            w = self.worlds(self.model, slot)
            stances = []
            for hip, (knee, ankle) in HIPS.items():
                verts = np.array(self.model.tmd.obj_verts(self.sk[ankle][0]))[:, :3]
                feet = [verts @ m[ankle][:3, :3].T + m[ankle][:3, 3] + [0, 0, root] for m, root in w]
                ground = max(f[:, 1].max() for f in feet)
                on = [f[:, 1] > ground - 1.5 for f in feet]
                stance = {t for t in range(ticks) if on[t].any()}
                self.assertGreaterEqual(len(stance), ticks * .3, (slot, hip))
                for t in range(ticks):
                    both = on[t] & on[t + 1]
                    if both.any():   # a sole point on the ground in two ticks stays where it is
                        slip = np.hypot(*(feet[t + 1][both] - feet[t][both])[:, [0, 2]].T).min()
                        self.assertLess(slip, 2, (slot, hip, t))
                stances.append(stance)
            right, left = stances
            shifted = {(t + ticks // 2) % ticks for t in right}
            self.assertGreaterEqual(len(shifted & left), len(left) - 2, slot)

    def test_knees_stay_beside_the_shell(self):
        for slot in SLOTS:
            for m, _ in self.worlds(self.model, slot):
                for hip, (knee, _) in HIPS.items():
                    h, k = m[hip][:3, 3], m[knee][:3, 3]
                    self.assertGreater(abs(k[0]) - abs(h[0]), 40, (slot, hip))   # out to the side, never in under the body
                    self.assertGreater(k[1] - h[1], -60, (slot, hip))           # never high over the hip (y is down)
                    self.assertGreater(k[2] - h[2], -45, (slot, hip))           # never far in front of the hip

    def test_thigh_and_shin_do_not_twist_round_their_length(self):
        # A leg that rolls about its own bone between 60 fps frames reads as legs churning round. Swing-twist split
        # of each step: the twist part (about the bone's own axis) stays small and sums to well under half a turn.
        def angle(r):
            return np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1, 1)))

        for slot in SLOTS:
            f = self.clip(self.model, slot)
            poses = [np.array(mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + [list(b) for b in p[1:]]))
                     for a, b in zip(f, f[1:]) for p in [interpolate_pose(a, b, al) for al in (0, 1365, 2730)]]
            for bone, child in ((10, 11), (11, 12), (13, 14), (14, 15)):
                rolls = []
                for prev, cur in zip(poses[-1:] + poses, poses):
                    local = prev[bone][:3, :3].T @ cur[bone][:3, :3]
                    axis = (np.linalg.inv(cur[bone]) @ cur[child][:, 3])[:3]
                    axis = axis / np.linalg.norm(axis)
                    moved = local @ axis
                    v, c = np.cross(axis, moved), float(axis @ moved)
                    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
                    rolls.append(angle((np.eye(3) + k + k @ k / (1 + c)).T @ local))
                self.assertLess(max(rolls), 20, (slot, bone))
                self.assertLess(sum(rolls), 120, (slot, bone))

    def test_hips_swing_without_spinning(self):
        # The engine lerps each stored Euler channel along its shortest arc (4096 units a turn), three steps a tick.
        # A hip channel that wraps, a cycle stored half a turn from the idle angles, a knee that circles the hip
        # once per stride or a big turn between two ticks all read as the hip spinning round.
        def angle(a, b):
            return np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))

        idle = self.clip(self.model, 1)[0]
        for slot in SLOTS:
            f = self.clip(self.model, slot)
            subs = [interpolate_pose(a, b, al) for a, b in zip(f, f[1:]) for al in (0, 1365, 2730)] + [f[-1]]
            poses = [np.array(mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + [list(b) for b in p[1:]]))
                     for p in subs]
            for hip, (knee, _) in HIPS.items():
                raw = np.array([p[hip][3:6] for p in f], dtype=float)
                steps = (np.diff(raw, axis=0) + 2048) % 4096 - 2048
                self.assertTrue((np.abs(np.diff(raw, axis=0)) == np.abs(steps)).all(), (slot, hip))   # no wrap
                track = raw[0] + np.concatenate([[[0, 0, 0]], np.cumsum(steps, axis=0)])
                self.assertLess(np.ptp(track, axis=0).max() * 360 / 4096, 60, (slot, hip))
                self.assertLess(np.abs(track[0] - idle[hip][3:6]).max() * 360 / 4096, 90, (slot, hip))
                rotations = [p[hip][:3, :3] for p in poses]
                for t in range(len(f) - 1):
                    path = sum(angle(rotations[3 * t + k], rotations[3 * t + k + 1]) for k in range(3))
                    self.assertLess(path, 30, (slot, hip, t))
                side = np.array([[p[knee][2, 3] - p[hip][2, 3], p[knee][1, 3] - p[hip][1, 3]] for p in poses])
                turn = np.unwrap(np.arctan2(side[:, 1], side[:, 0]))
                self.assertLess(abs(np.degrees(turn[-1] - turn[0])), 90, (slot, hip))   # 360 when it circles

    def test_in_between_frames_keep_the_hind_feet_out_of_the_floor(self):
        # The engine lerps the Euler angles between ticks (three steps at 60 fps).
        for slot in SLOTS:
            f = self.clip(self.model, slot)
            for a, b in zip(f, f[1:]):
                for alpha in (1365, 2730):
                    pose = interpolate_pose(a, b, alpha)
                    self.assertLess(F.A.floor(self.model, self.sk, pose, [ankle for _, ankle in HIPS.values()]), 6, slot)


if __name__ == '__main__':
    unittest.main()
