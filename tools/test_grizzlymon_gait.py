"""Check Grizzlymon's idle, walk, tired walk and run (species 296) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 296`; GRIZZLYMON_MODEL names another
path). Before the change it is `grizzlymon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import grizzlymon_gait as gait, quadruped, okuwamon_limbs

EXPECTED = '7b5a9d8a8c80f899ee319e14f5492b4ede5161b805c1c0174ee668149bb74e0e'
NB = 20
TICKS = {0: 96, 2: 24, 3: 28, 4: 15}
SPEED = {2: 15, 3: 11, 4: 38}
BODY = (1, 2, 3, 4, 8, 12, 16)
LEGS = {'RF': (5, 6, 7), 'LF': (9, 10, 11), 'RH': (13, 14, 15), 'LH': (17, 18, 19)}


class GrizzlymonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('GRIZZLYMON_MODEL', 'build/imported-model-edit/edit/296-Grizzlymon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 296')
        cls.rig = json.loads(Path('content/species/296-grizzlymon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[296] = cls.rig
        mmd.exe().bone_count[296] = NB
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 296
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 296

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, NB, slot)[0]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_cycle_lengths_and_speed_order(self):
        fr = {s: self.frames(s) for s in TICKS}
        self.assertEqual({s: len(f) - 1 for s, f in fr.items()}, TICKS)
        speed = {s: -(fr[s][-1][0][8] - fr[s][0][0][8]) / (len(fr[s]) - 1) for s in SPEED}
        self.assertEqual(speed, SPEED)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        for s, (low, high) in quadruped.SPEED_RANGE.items():
            self.assertTrue(low <= speed[s] <= high, s)
        for s in SPEED:       # one constant root speed
            f = fr[s]
            self.assertEqual(len({round(f[i + 1][0][8] - f[i][0][8], 6) for i in range(len(f) - 1)}), 1, s)

    def test_loops_are_seamless(self):
        for s in TICKS:
            f = self.frames(s)
            for a, b in zip(f[0][1:], f[-1][1:]):
                self.assertLess(max(abs(x - y) for x, y in zip(a[:6], b[:6])), 3, s)

    def test_only_the_field_clips_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        from motiondiscidentity import changed_programs
        self.assertEqual(changed_programs(self.old, self.new), self.report['changed_slots'])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        storage = motionstorage.audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_body_moves_like_a_heavy_bear(self):
        """The chest rolls and shifts sideways in the walk and the tired walk, and the head hangs lower than the chest."""
        for s in (2, 3):
            f = self.frames(s)[:-1]
            roll = [p[1][5] for p in f]
            shift = [p[1][6] for p in f]
            self.assertGreater(max(roll) - min(roll), 25, s)          # about 2.5 degrees or more of 4096
            self.assertGreater(max(shift) - min(shift), 12, s)

    def test_the_bear_is_menacing(self):
        """Minimum amplitudes: the head is pushed out ahead of the shoulders (local z is forward-negative; the rest is -151)
        and hangs low, the chest rolls hard over the planted paw, each fore landing drops the body, and the idle sweeps the
        head wide and slowly with the jaw opening in growls."""
        for s in (2, 3, 4):
            f = self.frames(s)[:-1]
            self.assertLessEqual(max(p[2][8] for p in f), -151 - 8, s)          # never less than 8 units ahead of the rest
            self.assertLessEqual(min(p[2][8] for p in f), -151 - 20, s)         # and lunging 20 or more
            self.assertGreaterEqual(min(p[2][7] for p in f), -42 + 6, s)        # hangs lower than the rest
            roll = [p[1][5] for p in f]
            self.assertGreater(max(roll) - min(roll), (80 if s != 4 else 60), s)    # 7 / 5 degrees peak to peak
            y = [p[1][7] for p in f]
            self.assertGreater(max(y) - min(y), 8, s)                           # the weight drop of the landings
        idle = self.frames(0)[:-1]
        yaw = [p[2][4] for p in idle]
        self.assertGreater(max(yaw) - min(yaw), 300)                            # 26 degrees of sweep
        self.assertGreater(max(p[3][3] for p in idle) - min(p[3][3] for p in idle), 60)   # the jaw opens
        self.assertGreater(max(p[2][3] for p in idle) - min(p[2][3] for p in idle), 80)   # the head sinks and rises

    def test_aggression_is_smooth_not_nervous(self):
        """Power without flutter: no bone's rotation jumps between ticks, and the head's yaw and thrust move on slow curves."""
        for s in TICKS:
            f = self.frames(s)[:-1]
            n = len(f)
            for bone in (1, 2, 3, 12, 16):
                for axis in (3, 4, 5):
                    series = [p[bone][axis] for p in f]
                    step = max(abs(series[(i + 1) % n] - series[i]) for i in range(n))
                    self.assertLess(step, 45 if s else 36, (s, bone, axis, step))       # 4 degrees a tick (3 in the idle)
            z = [p[2][8] for p in f]
            self.assertLess(max(abs(z[(i + 1) % n] - z[i]) for i in range(n)), 12, s)

    def test_feet_plant_and_the_floor_holds(self):
        for c in self.report['checks'] if self.old is not None else []:
            if c['slot'] == 0:
                continue
            self.assertLess(max(c['stance_slip'].values()), 0.25, c['slot'])
            self.assertLessEqual(c['lowest_point'], 3, c['slot'])

    def test_legs_do_not_cut_the_body(self):
        """Counted on every third tick: the fore legs may graze their shoulder pad by a few vertices (the walk swings
        them further than the imported clips did), the hind legs never touch the body."""
        np = self.np
        body = okuwamon_limbs.Body(self.new, self.rig)
        for s in (2, 3, 4):
            frames = self.frames(s)[:-1]
            worst = {k: 0 for k in LEGS}
            for pose in frames[::3]:
                mats, world = body.world(pose)
                for k, ch in LEGS.items():
                    others = BODY + tuple(b for kk, c in LEGS.items() if kk != k for b in c)
                    n = body.count(mats, world, ch[1:], others)
                    worst[k] = max(worst[k], n)
            self.assertEqual(worst['RH'] + worst['LH'], 0, (s, worst))
            self.assertLessEqual(max(worst['RF'], worst['LF']), 20, (s, worst))


if __name__ == '__main__':
    unittest.main()
