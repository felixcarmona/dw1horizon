"""Check Okuwamon's idle and four-legged clips on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 259`). Before the change it is
`okuwamon_limbs.SOURCE`: the generator is run on it (about 15 s) and its bytes are checked; afterwards it is the result
itself and the checks that need the old clips are skipped.
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
from tools.models.field_animations import okuwamon_limbs as limbs

EXPECTED = '079fbe4eeb5bdbfb03bb8cdfd3d7165a3203ac85d86f3f2f260242da1d57b3bc'
IDLE_PROGRAM = '408650295080d2af30eb8cb4c1b92aa8f68c45496dc24f1b5d70359fcc5e0964'     # slot 0 as the first pass left it
NB = 24
SLOTS = (0, 1, 2, 3, 4)
GAITS = (2, 3, 4)


class OkuwamonLimbs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/259-Okuwamon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 259')
        cls.rig = json.loads(Path('content/species/259-okuwamon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[259] = cls.rig
        mmd.exe().bone_count[259] = NB
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == limbs.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 259
            data, cls.proof = limbs.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 259
        cls.body = limbs.Body(cls.new, cls.rig)
        cls.base = cls.frames(0)[0]

    @classmethod
    def frames(cls, slot, model=None):
        return animsheet.slot_frames(model or cls.new, NB, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_idle_is_the_first_pass_byte_for_byte(self):
        self.assertEqual(hashlib.sha256(self.new.anims.anims[self.new.anims.table[0]].build()).hexdigest(), IDLE_PROGRAM)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_only_the_animations_differ(self):
        self.need_old()
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_gaits_stand_slide_and_turn_as_a_four_legged_walk_should(self):
        for slot in GAITS:
            spec = limbs.CLIPS[slot]
            report = limbs.clip_report(self.body, self.frames(slot), spec, self.base)
            self.assertEqual(limbs.clip_failures(report, spec), [], slot)
            self.assertEqual(report['ticks'], spec['n'])
            for leg in report['legs']:
                self.assertGreaterEqual(leg['stance'], 2, slot)
                self.assertLessEqual(leg['slip_mean'], limbs.SLIP_MEAN, slot)
                self.assertLessEqual(leg['slip_max'], limbs.SLIP_MAX, slot)
                self.assertLessEqual(leg['lowest'], 1.0, slot)           # nothing sinks into the floor

    def test_the_tired_rest_closes_and_stays_clear(self):
        spec = limbs.CLIPS[1]
        report = limbs.clip_report(self.body, self.frames(1), spec, self.base)
        self.assertEqual(limbs.clip_failures(report, spec), [])

    def test_diagonal_pairs_touch_down_together(self):
        for slot in GAITS:
            frames = self.frames(slot)
            n = len(frames) - 1
            down = []
            for k, (hip, knee) in enumerate(limbs.LEGS):
                lows = [float(np.max(self.body.points(self.body.world(f)[1], (knee,))[:, 1])) for f in frames[:n]]
                down.append([i for i in range(n) if lows[i] > -limbs.STANCE_FLOOR >= lows[i - 1]])
            self.assertEqual(down[0], down[3], slot)           # front right with hind left
            self.assertEqual(down[1], down[2], slot)           # front left with hind right
            self.assertEqual((down[1][0] - down[0][0]) % n, n // 2, slot)

    def test_speeds_stay_native_and_ordered(self):
        speed = {s: limbs.CLIPS[s]['v'] for s in GAITS}
        self.assertTrue(10 <= speed[3] <= 20 and 15 <= speed[2] <= 31 and 35 <= speed[4] <= 52, speed)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        for slot in GAITS:
            frames = self.frames(slot)
            self.assertEqual([-f[0][8] for f in frames], [limbs.CLIPS[slot]['v'] * i for i in range(len(frames))])

    def test_pincers_are_carried_forward_and_hang_lower_when_tired(self):
        def claw_z(slot):
            return np.mean([[np.array(self.body.world(f)[0][c], float)[2, 3] for c in (9, 12)] for f in self.frames(slot)[:-1]])
        idle = claw_z(0)
        for slot in (2, 4):
            self.assertLess(claw_z(slot), idle - 10, slot)           # forward is -z
        self.assertLess(claw_z(4), claw_z(2))                        # a little more forward in the run

        def claw_y(slot):
            return np.mean([[np.array(self.body.world(f)[0][c], float)[1, 3] for c in (9, 12)] for f in self.frames(slot)[:-1]])
        self.assertGreater(claw_y(3), claw_y(2))                     # y is down

    def test_the_body_sways_from_side_to_side_over_the_planted_feet(self):
        degrees = 4096 / 360
        least = {2: (30, 6, 5), 3: (36, 8, 6), 4: (20, 6, 4)}       # pelvis shift, roll, yaw (peak to peak); the tired walk sways most
        for slot in GAITS:
            frames = self.frames(slot)[:-1]
            shift, roll, yaw = (np.ptp([f[1][i] for f in frames]) for i in (6, 5, 4))
            self.assertGreaterEqual(shift, least[slot][0], slot)
            self.assertLessEqual(shift, 60, slot)                          # the feet are 250 across, the hips 100 a side
            self.assertGreaterEqual(roll / degrees, least[slot][1], slot)
            self.assertGreaterEqual(yaw / degrees, least[slot][2], slot)
            heads = [np.array(self.body.points(self.body.world(f)[1], (5, 6)))[:, 0].mean() - np.array(self.body.world(f)[0][1], float)[0, 3]
                     for f in frames]
            self.assertGreater(np.ptp(heads), 12, slot)                    # the head follows
            self.assertGreater(np.ptp([f[3][5] for f in frames]), 10, slot)    # the chest leans after the pelvis
        self.assertGreater(np.ptp([f[1][6] for f in self.frames(3)[:-1]]), np.ptp([f[1][6] for f in self.frames(4)[:-1]]))

    def test_loops_are_seamless_and_wings_move(self):
        for slot in SLOTS:
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:], slot)
            for b in limbs.WINGS:
                span = max(max(f[b][3 + c] for f in frames) - min(f[b][3 + c] for f in frames) for c in range(3))
                self.assertGreater(span, 4, (slot, b))               # no frozen wing or elytra (4096 units a turn)

    def test_every_alias_of_the_five_slots_changes_with_them(self):
        self.need_old()
        self.assertEqual(self.proof['changed_slots'], [0, 1, 2, 3, 4, 14, 15, 16, 17, 18, 23, 34, 35, 36])


if __name__ == '__main__':
    unittest.main()
