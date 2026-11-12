"""Check Ghoulmon's walk, tired walk and run (species 329) on the real import: planted feet under a living body.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 329`; GHOULMON_MODEL names another
path). Before the change it is `ghoulmon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself and the checks that need the old clips are skipped.

Bones: upper body 1 (torso, head, horns), wings 2-3 / 10-11, arms 4-9 / 12-17, hips 18, tail 19-21, right leg 22-25
(thigh, shin, ankle plate, claws), left leg 26-29.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import ghoulmon_gait as gait, meshclash

DEG = 4096 / 360
EXPECTED = '9b2832adc563bb2656390c871b65821cf6ccc42f73f06b776ff6fcc75f2b8798'
BONES = 30
TICKS = {2: 26, 3: 34, 4: 14}
SPEED = {2: 17, 3: 11, 4: 38}
RIGHT, LEFT = [22, 23, 24, 25], [26, 27, 28, 29]
TOES = {'RH': 25, 'LH': 29}
ARMS = list(range(4, 10)) + list(range(12, 18))
WINGS, TAIL = [2, 3, 10, 11], [19, 20, 21]
# the leg tops already overlap the hips this much at rest (37 triangle crossings); no clip makes it worse
LEGS_IN_HIPS = 37
ARMS_IN_BODY = 24            # the rest pose's own overlaps; no clip makes them worse
WINGS_IN_BODY = 18


class GhoulmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('GHOULMON_MODEL', 'build/imported-model-edit/edit/329-Ghoulmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 329')
        cls.rig = json.loads(Path('content/species/329-ghoulmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[329] = cls.rig
        mmd.exe().bone_count[329] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 329
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 329
        cls.tim = path.with_suffix('.TIM')

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot):
        rows = []
        for pose in self.frames(slot):
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            mats = mmd.bone_matrices(self.new, p)
            rows.append({n: (mats[b][0][3], -mats[b][1][3] - pose[0][7], mats[b][2][3] + pose[0][8]) for n, b in TOES.items()})
        return rows

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_three_clips_change_and_the_idle_is_kept(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), [2, 3, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())           # the mesh (the proportions) is untouched
        self.assertEqual(self.frames(0, self.old), self.frames(0))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(steps, {-SPEED[slot]}, slot)                  # the same step every tick
            speeds[slot] = SPEED[slot]
        self.assertTrue(speeds[3] < speeds[2] < speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(frames[0][b][i] - frames[-1][b][i]), 1, (slot, b, i))

    def test_the_upper_body_is_alive(self):
        """The torso turns against the hips, the arms swing, the wings flap and the tail follows, in every clip."""
        def spread(slot, bone, axis):
            values = [f[bone][axis] for f in self.frames(slot)[:-1]]
            d = max(values) - min(values)
            return min(d, 4096 - d) / DEG
        for slot in TICKS:
            self.assertGreater(spread(slot, 1, 4) + spread(slot, 1, 5), 4, slot)               # torso yaw and roll
            self.assertGreater(max(spread(slot, b, 3) for b in (4, 12)), 5, slot)           # an arm swings
            self.assertGreater(spread(slot, 3, 5) + spread(slot, 11, 5), 2, slot)           # the wing membranes
            self.assertGreater(max(spread(slot, b, 3) + spread(slot, b, 4) for b in (20, 21)), 5, slot)   # tail
            heights = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreater(max(heights) - min(heights), 6, slot)                         # the body bobs

    def test_the_legs_alternate_half_a_cycle_apart(self):
        for slot in (2, 4):
            rows = self.feet(slot)[:-1]
            n = len(rows)
            for t in range(n):
                self.assertAlmostEqual(rows[t]['RH'][1], rows[(t + n // 2) % n]['LH'][1], delta=4, msg=(slot, t))

    def test_the_feet_are_planted_in_stance_and_lift_in_swing(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                ground = min(r[name][1] for r in rows)       # the toe point stands about 25 units over the sole at rest
                stance = [i for i, r in enumerate(rows) if r[name][1] < ground + 6]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), 20, (slot, name))                 # never sunk
                self.assertGreater(max(heights) - min(heights), 20, (slot, name))

    def test_the_studio_measures_no_slide_in_stance(self):
        import animstudio
        import tempfile
        tmp = tempfile.mkdtemp()
        Path(tmp, 'm.MMD').write_bytes(self.data)
        Path(tmp, 'm.TIM').write_bytes(self.tim.read_bytes())
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{tmp}/m.MMD:329:{tmp}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 15, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def test_no_tick_jumps(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('needs numpy')
        clash = meshclash.Clash(self.new, self.rig)
        for slot in TICKS:
            speeds, prev = [], None
            for pose in self.frames(slot):
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = np.asarray(clash.world(p), float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            self.assertLess(max(speeds), 2.5 * sorted(speeds)[len(speeds) // 2], slot)

    def test_no_new_penetration(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest('needs numpy')
        clash = meshclash.Clash(self.new, self.rig)
        for slot in TICKS:
            frames = self.frames(slot)[:-1]
            self.assertEqual(max(clash.clash(p, RIGHT, LEFT)[0] for p in frames), 0, slot)
            self.assertEqual(max(clash.clash(p, LEFT, RIGHT)[0] for p in frames), 0, slot)
            self.assertLessEqual(max(clash.clash(p, RIGHT + LEFT, [18])[0] for p in frames), LEGS_IN_HIPS, slot)
            self.assertEqual(max(clash.clash(p, RIGHT + LEFT, [1])[0] for p in frames), 0, slot)
            self.assertEqual(max(clash.clash(p, ARMS, RIGHT + LEFT)[0] for p in frames), 0, slot)
            self.assertLessEqual(max(clash.clash(p, ARMS, [1])[0] for p in frames), ARMS_IN_BODY, slot)
            self.assertLessEqual(max(clash.clash(p, WINGS, TAIL + [1, 18])[0] for p in frames), WINGS_IN_BODY, slot)


if __name__ == '__main__':
    unittest.main()
