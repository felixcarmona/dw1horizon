"""Check Scorpiomon's four hovering-swimmer clips on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 275`). Before the change it is
`scorpiomon_swim.SOURCE`: the generator is run on it (about 2 s) and its bytes are checked; afterwards it is the result
itself and the checks that need the old clips are skipped. The model has no legs and never touches the floor, so
instead of planted feet the checks are the ones a swimmer can fail: four different movements, closed loops, the speed
order, bounded joint speeds, a clear gap to the floor, limbs that stay out of each other, and the storage budget.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import scorpiomon_swim as swim
from tools.models.field_animations.meshclash import Clash

EXPECTED = '5cedf12ea38bce6d31c8b55642323abb72fb3cf1eb0f9db8c5f5001ef2dc3224'
NB = swim.NB
TICKS = {0: 64, 2: 32, 3: 44, 4: 20}
SPEEDS = {0: 0, 2: 26, 3: 14, 4: 42}
IDENT = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
# the import's own limbs already cross at rest: the face plate with the claws' roots and the blades' roots (pairs of
# triangles, deepest crossing in units). The clips may not cross more than that, nor any other pair of parts.
BASELINE = {'claws-head': (22, 13.9), 'blades-body': (24, 11.9)}
PAIRS = {
    'claws-head': ((7, 8, 9, 10, 11, 12), (2, 3, 4, 5, 6)),
    'blades-body': ((13, 14, 15, 16), (1, 2, 17, 18)),
    'claw_R-claw_L': ((7, 8, 9), (10, 11, 12)),
    'claws-blades': ((7, 8, 9, 10, 11, 12), (13, 14, 15, 16)),
    'blade_R-blade_L': ((13, 14), (15, 16)),
    'tail-body': ((20, 21, 22), (1,)),
    'fan-spikes': ((22,), (1, 17, 18)),
    'tail-17-19': ((17,), (19,)), 'tail-18-20': ((18,), (20,)), 'tail-19-21': ((19,), (21,)), 'tail-20-22': ((20,), (22,)),
    'blades-tail': ((13, 14, 15, 16), (17, 18, 19, 20, 21, 22)),
}


class ScorpiomonSwim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/275-Scorpiomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 275')
        cls.rig = json.loads(Path('content/species/275-scorpiomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(275, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == swim.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 275
            data, cls.report = swim.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 275

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, NB, slot)

    def angles(self, slot):
        """Local joint angles in degrees, unwrapped along the loop (ticks+1 x bones x 3)."""
        frames = self.frames(slot)[0]
        a = np.array([[v[3:6] for v in p[1:]] for p in frames], float) * 360 / 4096
        return np.degrees(np.unwrap(np.radians((a + 180) % 360 - 180), axis=0, period=2 * np.pi))

    def world(self, slot, bone, axis):
        return np.array([mmd.bone_matrices(self.model, [IDENT] + p[1:])[bone][axis][3] for p in self.frames(slot)[0][:-1]])

    def test_the_bytes_are_the_recorded_result(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                swim.build(self.data + b'x', self.rig)

    def test_only_the_four_clips_and_their_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), {0, 1, 2, 3, 4, 18})
        self.assertEqual(self.frames(1)[0], self.frames(0)[0])           # the idle's aliases follow it
        self.assertEqual(self.frames(18)[0], self.frames(0)[0])

    def test_each_clip_has_its_own_length_and_the_same_distance_every_tick(self):
        self.assertEqual(len({len(self.frames(s)[0]) for s in TICKS}), 4)
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)[0]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertEqual({frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}, {-SPEEDS[slot]}, slot)
            self.assertEqual(frames[-1][0][6:8], frames[0][0][6:8])

    def test_speeds_are_native_and_ordered(self):
        self.assertTrue(15 <= SPEEDS[2] <= 31 and 10 <= SPEEDS[3] <= 20 and 35 <= SPEEDS[4] <= 52)
        self.assertLess(SPEEDS[3], SPEEDS[2])
        self.assertLess(SPEEDS[2], SPEEDS[4])

    def test_the_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)[0]
            for b in range(1, NB):
                for x, y in zip(frames[0][b], frames[-1][b]):
                    self.assertLessEqual(min((x - y) % 4096, (y - x) % 4096), 1, (slot, b))

    def test_the_four_clips_move_differently(self):
        stats = {s: (self.angles(s)[:-1].mean(0), self.angles(s)[:-1].std(0)) for s in TICKS}
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    self.assertGreater(float(np.abs(stats[a][0] - stats[b][0]).max()), 2.5, (a, b))     # a different posture
                    self.assertGreater(float(np.abs(stats[a][1] - stats[b][1]).max()), 1.5, (a, b))    # and amount of motion

    def local(self, slot, bone):
        """The bone's position in the carapace's own frame (x right, y down, z back), per tick."""
        out = []
        for p in self.frames(slot)[0][:-1]:
            m = mmd.bone_matrices(self.model, [IDENT] + p[1:])
            r, o = np.array([row[:3] for row in m[1][:3]]), np.array([m[1][i][3] for i in range(3)])
            out.append(r.T @ (np.array([m[bone][i][3] for i in range(3)]) - o))
        return np.array(out)

    def test_posture_reads_as_the_clip_should(self):
        claw_y = {s: np.mean([self.local(s, b)[:, 1].mean() for b in (9, 12)]) for s in TICKS}    # y is down
        self.assertGreater(claw_y[3], claw_y[2] + 30)                  # the tired claws hang lower than the walk's
        self.assertLess(claw_y[4], claw_y[2] - 25)                     # the run tucks them up under the face
        fan_y = {s: self.world(s, 22, 1).mean() - self.world(s, 1, 1).mean() for s in TICKS}      # world, relative to the body
        self.assertGreater(fan_y[3], fan_y[2] + 30)                    # the tired tail trails low
        self.assertLess(fan_y[4], fan_y[2] - 20)                       # the run's tail is raised
        low = {s: max(max(v[1] for tri in animsheet.world_tris(self.model, [IDENT] + p[1:], self.rig) for v in tri[0])
                      for p in self.frames(s)[0]) for s in TICKS}
        for slot in TICKS:
            self.assertLess(low[slot], -90, slot)                       # y points down: the floor is 0, it hovers
        self.assertGreater(low[3] - low[2], 25)                        # the tired body sinks, by its lowest point
        head_pitch = {s: np.mean([f[2][3] for f in self.frames(s)[0][:-1]]) for s in TICKS}
        self.assertNotEqual(round(head_pitch[3]), round(head_pitch[2]))

    def test_body_bob_sway_and_roll_in_the_travelling_clips(self):
        for slot, (bob, sway, roll) in {0: (8, 3, 1.5), 2: (14, 10, 6), 3: (14, 8, 4), 4: (8, 12, 6)}.items():
            self.assertGreaterEqual(float(np.ptp(self.world(slot, 1, 1))), bob, slot)
            self.assertGreaterEqual(float(np.ptp(self.world(slot, 1, 0))), sway, slot)
            self.assertGreaterEqual(float(np.ptp([f[1][5] for f in self.frames(slot)[0][:-1]])) * 360 / 4096, roll, slot)

    def test_claws_blades_and_tail_move_in_every_clip(self):
        least = {0: (14, 4, 20), 2: (20, 10, 35), 3: (12, 6, 20), 4: (20, 12, 20)}      # claw tip, blade tip, tail fan (units)
        for slot, (claw, blade, tail) in least.items():
            for b in (9, 12):
                self.assertGreaterEqual(max(float(np.ptp(self.world(slot, b, i))) for i in range(3)), claw, (slot, b))
            for b in (14, 16):
                rel = [self.world(slot, b, i) - self.world(slot, 1, i) for i in range(3)]
                self.assertGreaterEqual(max(float(np.ptp(r)) for r in rel), blade, (slot, b))
            rel = [self.world(slot, 22, i) - self.world(slot, 1, i) for i in range(3)]
            self.assertGreaterEqual(max(float(np.ptp(r)) for r in rel), tail, slot)

    def test_a_wave_runs_down_the_tail_and_the_blades_row_in_turn(self):
        for slot in (2, 3, 4):
            ys = np.array([self.local(slot, b)[:, 1] for b in (19, 21, 22)])
            f = np.fft.rfft(ys - ys.mean(1, keepdims=True), axis=1)[:, 1]
            step = ((np.diff(np.angle(f)) / (2 * np.pi) + .5) % 1) - .5       # cycles each segment trails the one before
            self.assertTrue(bool((step < -.02).all()), (slot, step))   # every segment follows later: a travelling wave
            self.assertLess(float(step.sum()), -.08, slot)
            right, left = (np.array([self.world(slot, b, 1) - self.world(slot, 1, 1)]).ravel() for b in (14, 16))
            fr, fl = (np.fft.rfft(x - x.mean())[1] for x in (right, left))
            shift = abs(((np.angle(fl) - np.angle(fr) + np.pi) % (2 * np.pi)) - np.pi)
            self.assertGreater(float(shift), 1.2, slot)                # the blades stroke in turn, not together

    def test_no_snap_no_hold_and_no_rapid_beat(self):
        for slot in TICKS:
            a = self.angles(slot)
            d = np.abs(np.diff(a, axis=0)).reshape(TICKS[slot], -1)
            moving = d[:, np.ptp(a.reshape(len(a), -1), axis=0) > 8.]
            self.assertGreaterEqual(moving.shape[1], 5, slot)
            ratio = float((moving.max(0) / np.median(moving, 0)).max())
            self.assertLess(ratio, 2.75, slot)                         # no tick beyond about 2.5 times the median
            hold = float((moving < .1 * moving.max(0)).mean())
            self.assertLess(hold, .12, slot)
            body = a[:-1].reshape(TICKS[slot], -1)
            body = body[:, np.ptp(body, axis=0) > 5.]
            power = np.abs(np.fft.rfft(body - body.mean(0), axis=0)) ** 2
            share = power / power[1:].sum(0)
            self.assertLess(float(share[TICKS[slot] // 3:].sum(0).max()), .02, slot)   # nothing at three ticks or less

    def test_limbs_stay_out_of_each_other_no_worse_than_the_import(self):
        clash = Clash(self.model, self.rig)
        for slot in TICKS:
            frames = self.frames(slot)[0][:-1]
            for name, (a, b) in PAIRS.items():
                worst = (0, 0.)
                for f in frames[::2]:
                    r = clash.clash(f, list(a), list(b))
                    worst = max(worst, r)
                limit = BASELINE.get(name, (0, 0.))
                self.assertLessEqual(worst[0], limit[0] + 1, (slot, name, worst))            # at most one pair more than the import's rest pose
                self.assertLessEqual(worst[1], limit[1] + 1.5, (slot, name, worst))

    def test_sounds_and_storage(self):
        if self.old is not None:
            for slot in (2, 3, 4):
                self.assertEqual(len(self.frames(slot)[2]), len(self.frames(slot, self.old)[2]), slot)
        storage = motionstorage.require(self.data, NB)
        self.assertLess(storage['resident_bytes'], storage['resident_limit'])
        self.assertLessEqual(storage['resident_limit'], 100352)
        self.assertTrue(motionstorage.audit(self.data, NB)['fits'])


if __name__ == '__main__':
    unittest.main()
