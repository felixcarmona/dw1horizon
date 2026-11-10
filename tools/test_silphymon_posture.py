"""Silphymon's idle, walk, condition walk and run hang the wing-arms at its sides and walk on the floor.

Needs the stored model (tools/models/edit.py get 226 writes it to build/imported-model-edit/edit)."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd

SOURCE = Path(os.environ.get('SILPHYMON_MODEL', 'build/imported-model-edit/edit/226-Silphymon.MMD'))
NB = 21
TICKS = {0: 48, 2: 16, 3: 16, 4: 16}
SPEED = {0: 0, 2: 22.5, 3: 20, 4: 50}


class SilphymonPosture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('needs the imported Silphymon model (tools/models/edit.py get 226)')
        record = json.loads(next(Path('content/species').glob('226-*.json')).read_text())
        cls.skeleton = [tuple(b) for b in record['model']['skeleton']]
        mmd.exe().add_type(226, cls.skeleton)
        cls.model = mmd.MMD.parse(SOURCE.read_bytes(), NB)
        cls.model.type = 226
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s) for s in (0, 1, 2, 3, 4)}
        cls.verts = {b: [list(v[:3]) for v in cls.model.tmd.obj_verts(cls.skeleton[b][0])] for b in range(1, NB)}

    def world(self, pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.model, pose)

    def test_loops_are_seamless_and_keep_the_field_speed(self):
        for slot, ticks in TICKS.items():
            frames, loop, _ = self.clips[slot]
            self.assertEqual((len(frames) - 1, loop), (ticks, 0))
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))
            speed = (frames[0][0][8] - frames[-1][0][8]) / ticks
            self.assertAlmostEqual(speed, SPEED[slot], places=3)

    def test_footstep_sounds_keep_their_ticks(self):
        ticks = {slot: [t for t, kind, _ in self.clips[slot][2] if kind == 'sound'] for slot in (2, 3, 4)}
        self.assertEqual(ticks, {2: [2, 10], 3: [0, 8], 4: [2, 10]})

    def test_arms_hang_by_the_body_and_are_never_raised(self):
        for slot in TICKS:
            for pose in self.clips[slot][0]:
                w = self.world(pose)
                for shoulder, hand, side in ((6, 8, 1), (9, 11, -1)):
                    s, h = w[shoulder], w[hand]
                    # the hand stays below the shoulder and beside the body (no wing held out to the side)
                    self.assertGreater(h[1][3] - s[1][3], 30, (slot, hand))
                    self.assertLess(abs(h[0][3]) - abs(s[0][3]), 80, (slot, hand))
                    self.assertGreater(side * h[0][3], 20, (slot, hand))

    def test_feet_stand_on_the_floor_and_nothing_else_digs_in(self):
        for slot in TICKS:
            frames = self.clips[slot][0]
            lows = []
            for pose in frames:
                w = self.world(pose)
                body = max(max(sum(w[b][1][k] * v[k] for k in range(3)) + w[b][1][3] for v in self.verts[b])
                           for b in range(1, NB) if b not in (14, 15, 18, 19))
                self.assertLess(body, 1, slot)
                lows.append(max(max(sum(w[b][1][k] * v[k] for k in range(3)) + w[b][1][3] for v in self.verts[b])
                                for b in (14, 15, 18, 19)))
            # the lowest sole point reaches the floor in every clip and never goes under it
            self.assertLess(max(lows), 3, slot)
            self.assertGreater(max(lows), -3, slot)

    def test_every_step_is_a_heel_strike_roll_and_toe_off(self):
        # foot pitch in degrees, + toes down: toes up as the foot lands, rolling flat, the heel rising before toe-off
        need = {2: (30, 12, 10), 3: (22, 6, 8), 4: (30, 6, 10)}      # total range, toes-up at strike, toes-down at off
        for slot, (span, up, down) in need.items():
            frames = self.clips[slot][0]
            for ankle, toe in ((14, 15), (18, 19)):
                pitch, floor = [], []
                for pose in frames[:-1]:
                    w = self.world(pose)
                    pitch.append(math.degrees(math.asin(-w[ankle][1][2])))
                    floor.append(max(sum(w[b][1][k] * v[k] for k in range(3)) + w[b][1][3]
                                     for b in (ankle, toe) for v in self.verts[b]))
                self.assertGreaterEqual(max(pitch) - min(pitch), span, (slot, ankle))
                self.assertLessEqual(min(pitch), -up, (slot, ankle))
                self.assertGreaterEqual(max(pitch), down + 6, (slot, ankle))
                n = len(pitch)
                landings = [i for i in range(n) if floor[i] > -2 and floor[i - 1] < -2]
                self.assertEqual(len(landings), 1, (slot, ankle, floor))
                self.assertLessEqual(pitch[landings[0]], -up * .5, (slot, ankle))
                # the heel is up and the toes still on the floor at the last grounded tick (toe-off)
                last = max(i for i in range(n) if floor[i] > -2 and floor[(i + 1) % n] < -2)
                self.assertGreaterEqual(pitch[last], down, (slot, ankle))


if __name__ == '__main__':
    unittest.main()
