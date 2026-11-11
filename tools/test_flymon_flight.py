"""Flymon's idle, walk, condition walk and run are four different, seamless flights that keep the field speeds in order.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 262`). Before the change it is
`flymon_flight.SOURCE`: the generator is run on it (a few seconds); afterwards it is the result itself and the checks
that need the old clips are skipped. `python3 tools/test_flymon_flight.py report` prints the numbers quoted in the docs."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
import motionstorage
from tools.models.field_animations import flymon_flight as flight
from tools.models.field_animations import meshclash
from tools.models.field_animations.okuwamon_limbs import DIRS, inside

EXPECTED = '35d960acbab89c60a85ccb2e61867e58e823c37406e756c728a78c0fcac0e204'
NB = 29
BODY = (1, 2, 3)
GROUPS = {'legL': (8, 9, 10, 11, 12), 'legR': (13, 14, 15, 16, 17), 'armLF': (18, 19), 'armLR': (22, 23),
          'armRF': (20, 21), 'armRR': (24, 25), 'wingL': (4,), 'wingR': (5,), 'wingLu': (6,), 'wingRu': (7,)}
SOCKET = 60.0        # units around a limb's root joint, built into the body (as the rest pose is)
SPEED = {2: 18, 3: 13, 4: 38}
TICKS = {0: 30, 2: 30, 3: 40, 4: 20}
BEATS = {0: 2, 2: 3, 3: 2, 4: 4}


class FlymonFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/262-Flymon.MMD')
        if not path.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 262 (needs the player DW1 extraction)')
        cls.rig = json.loads(Path('content/species/262-flymon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(262, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == flight.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 262
            data, _ = flight.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 262
        cls.clips = {s: animsheet.slot_frames(cls.new, NB, s) for s in (0, 1, 2, 3, 4)}
        cls.mesh = animstudio.FastMesh(type('M', (), dict(m=cls.new, skel=cls.rig))())

    def frames(self, slot):
        return self.clips[slot][0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        mats = mmd.bone_matrices(self.new, p)
        return mats, self.mesh.world(mats).astype(float)

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_storage_fits_the_resident_buffer(self):
        storage = motionstorage.audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_only_the_five_field_slots_change(self):
        if self.old is not None:
            self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
            self.assertEqual(flight.changed_programs(self.old, self.new), [0, 1, 2, 3, 4])

    def test_tick_counts_and_speeds_are_in_order(self):
        for slot, n in TICKS.items():
            self.assertEqual(len(self.frames(slot)) - 1, n, slot)
        for slot, speed in SPEED.items():
            self.assertEqual([-f[0][8] for f in self.frames(slot)], [speed * i for i in range(TICKS[slot] + 1)])
        self.assertEqual({f[0][8] for f in self.frames(0)}, {0})
        self.assertTrue(10 <= SPEED[3] < SPEED[2] < SPEED[4] <= 52)
        self.assertEqual(self.frames(1), self.frames(0))
        self.assertGreater(TICKS[3] / BEATS[3], TICKS[2] / BEATS[2])           # the heavy flight beats slower
        self.assertLess(TICKS[4] / BEATS[4], TICKS[2] / BEATS[2])              # the dash beats faster

    def test_loops_are_seamless(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            self.assertEqual(self.clips[slot][1], 0)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel])
                    self.assertLessEqual(min(gap % 4096, 4096 - gap % 4096) if channel < 6 else gap, 1, (slot, bone, channel))

    def test_the_four_clips_differ(self):
        def key(slot):
            return [[tuple(j[3:]) for j in f[1:]] for f in self.frames(slot)]
        for a in (0, 2, 3, 4):
            for b in (0, 2, 3, 4):
                if a < b:
                    # the rotations of the shared ticks: no two clips repeat each other's pose sequence
                    n = min(len(self.frames(a)), len(self.frames(b)))
                    same = sum(1 for x, y in zip(key(a)[:n], key(b)[:n]) if x == y)
                    self.assertLess(same, n // 4, (a, b))
        mean = {s: np.mean([self.pitch(f) for f in self.frames(s)[:-1]]) for s in (0, 2, 3, 4)}
        self.assertLess(mean[0], mean[2])
        self.assertLess(mean[2], mean[4] - 10)                 # the dash leans far more than the cruise
        self.assertGreater(mean[3] - mean[0], 5)               # the heavy flight is pitched and drooping
        self.assertGreater(np.ptp([self.pitch(f) for f in self.frames(3)[:-1]]), np.ptp([self.pitch(f) for f in self.frames(0)[:-1]]))

    def pitch(self, pose):
        """Degrees the body's vertical axis is tipped forward (about the across axis), from the head bone."""
        r = np.array(mmd.bone_matrices(self.new, [[4096] * 3 + [0] * 6] + [list(v) for v in pose[1:]])[1], float)
        return math.degrees(math.atan2(r[2][1], r[1][1]))

    def test_wings_beat_and_stay_on_their_hinges(self):
        rest = self.frames(0)[0]
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for bone in (4, 5, 6, 7):
                # translation of a wing is its hinge on the body: never changed, only turned
                self.assertTrue(all(f[bone][6:9] == rest[bone][6:9] for f in frames), (slot, bone))
            angle = np.array([f[5][5] for f in frames[:-1]], float)
            turns = sum(1 for a, b, c in zip(angle, np.roll(angle, -1), np.roll(angle, -2)) if (b - a) * (c - b) < 0)
            self.assertGreaterEqual(turns, 2 * BEATS[slot] - 2, slot)
            self.assertLessEqual(turns, 2 * BEATS[slot] + 4, slot)
            self.assertGreater(np.ptp(angle), 15, slot)
            self.assertLess(np.abs(np.diff(angle)).max(), 600, slot)             # no jump between two ticks
        # the dash beats smaller than the heavy flight
        self.assertLess(np.ptp([f[5][5] for f in self.frames(4)]), np.ptp([f[5][5] for f in self.frames(3)]))

    def test_nothing_goes_through_the_body_or_another_limb(self):
        for slot in (0, 2, 3, 4):
            worst = {}
            for pose in self.frames(slot)[:-1]:
                mats, w = self.world(pose)
                for name, group in GROUPS.items():
                    others = BODY + tuple(b for n, g in GROUPS.items() if n != name for b in g)
                    tri = w[self.mesh.tri[np.isin(self.mesh.bone, group)]]
                    points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    root = np.array(mats[group[0]], float)[:3, 3]
                    points = points[np.linalg.norm(points - root, axis=1) > SOCKET]
                    cage = w[self.mesh.tri[np.isin(self.mesh.bone, others)]]
                    votes = sum(inside(points, cage, d).astype(int) for d in DIRS)
                    worst[name] = max(worst.get(name, 0), int((votes >= 3).sum()))
            self.assertEqual({k: v for k, v in worst.items() if v}, {}, slot)

    def test_the_wings_of_a_side_never_cut_each_other(self):
        clash = meshclash.Clash(self.new, self.rig)
        for slot in (0, 2, 3, 4):
            for pose in self.frames(slot)[:-1]:
                world = clash.world(pose)
                self.assertEqual(clash.clash(pose, (4, 6), (5, 7), world)[0], 0, slot)
                self.assertEqual(clash.clash(pose, (4,), (6,), world)[0], 0, slot)
                self.assertEqual(clash.clash(pose, (5,), (7,), world)[0], 0, slot)

    def test_the_flyer_stays_above_the_floor(self):
        for slot in (0, 2, 3, 4):
            low = max(float(self.world(f)[1][:, 1].max()) for f in self.frames(slot)[:-1])
            self.assertLess(low, 0, slot)                                        # y is down: nothing sinks into the floor

    def test_limbs_and_abdomen_follow_later_than_the_body(self):
        # the abdomen and the legs reach their extremes after the body's: the lag is real, not a copy of the bob
        for slot in (0, 2, 4):
            frames = self.frames(slot)[:-1]
            body = np.array([f[1][7] for f in frames], float)
            for bone in (3, 9, 14, 19):
                signal = np.array([f[bone][3] + f[bone][4] + f[bone][5] for f in frames], float)
                if np.ptp(signal) < 2:
                    continue
                self.assertLess(abs(np.corrcoef(signal, body)[0, 1]), .995, (slot, bone))


def report():
    case = FlymonFlight
    case.setUpClass()
    t = case('test_the_four_clips_differ')
    for slot, name in ((0, 'idle'), (2, 'walk'), (3, 'tired'), (4, 'run')):
        frames = t.frames(slot)[:-1]
        pitch = [t.pitch(f) for f in frames]
        angle = [f[5][5] * 360 / 4096 for f in frames]
        legs = [f[9][3] * 360 / 4096 for f in frames]
        arms = [f[18][3] * 360 / 4096 for f in frames]
        print(slot, name, 'ticks', len(frames), 'speed', SPEED.get(slot, 0), 'beats', BEATS[slot],
              'pitch mean %.1f p-p %.1f' % (np.mean(pitch), np.ptp(pitch)), 'wing z p-p %.1f' % np.ptp(angle),
              'bob p-p %.0f' % np.ptp([f[1][7] for f in frames]), 'leg x p-p %.1f' % np.ptp(legs),
              'arm x p-p %.1f' % np.ptp(arms))


if __name__ == '__main__':
    if sys.argv[1:] == ['report']:
        report()
    else:
        unittest.main()
