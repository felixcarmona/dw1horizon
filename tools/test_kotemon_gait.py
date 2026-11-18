"""Check Kotemon's walk, tired walk and run (species 351) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 351`; KOTEMON_MODEL names another path).
The test runs the overlay's recipe (`imported_equipment.build`, which calls `kotemon_gait.build_clips`) and checks the result.

Kotemon faces -z: torso 1, skirt 2, tail 3-5, right leg 6-8 (thigh, foot block, claw plate), left leg 9-11, shoulder plates
12 and 22, arms 13-16 and 18-20, head 17. Both hands hold the shinai (16, with hidden copies 21 and 23).
"""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import imported_equipment

BONES = 24
TICKS = {2: 26, 3: 30, 4: 22}               # each clip is two cycles of 13, 15 and 11 ticks
SPEED = {2: 16, 3: 11, 4: 36}


class KotemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('KOTEMON_MODEL', 'build/imported-model-edit/edit/351-Kotemon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 351')
        cls.rig = json.loads(Path('content/species/351-kotemon.json').read_text())['model']['skeleton']
        cls.source = path.read_bytes()
        cls.data, cls.report = imported_equipment.build(cls.source, cls.rig)
        mmd.exe().skeleton[351] = cls.rig
        mmd.exe().bone_count[351] = BONES
        cls.old = mmd.MMD.parse(cls.source, BONES)
        cls.old.type = 351
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 351

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def test_only_the_three_walks_change(self):
        self.assertEqual(self.report['walking']['changed_slots'], [2, 3, 4])
        for slot in (0, 33):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old))

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
            self.assertEqual(len(steps), 1, slot)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(frames[0][b][i] - frames[-1][b][i]), 1, (slot, b, i))

    def test_the_studio_measures_no_slide_in_stance(self):
        import tempfile
        import animstudio
        tmp = tempfile.mkdtemp()
        Path(tmp, 'm.MMD').write_bytes(self.data)
        Path(tmp, 'm.TIM').write_bytes(Path(os.environ.get('KOTEMON_MODEL', 'build/imported-model-edit/edit/351-Kotemon.MMD')).with_suffix('.TIM').read_bytes())
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{tmp}/m.MMD:351:{tmp}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 7, (slot, bone))

    def test_the_soles_stay_near_the_floor(self):
        for item in self.report['walking']['checks']:
            self.assertLess(item['lowest_point'], 3, item['gait'])

    def test_both_hands_keep_their_grip_on_the_shinai(self):
        """The distance between the shinai (16) and its hidden copy (21), both on the hands, stays what the rest pose has."""
        rest = self.frames(0)[0]
        w = mmd.bone_matrices(self.new, [list(r) for r in rest])
        want = sum((w[16][i][3] - w[21][i][3]) ** 2 for i in range(3)) ** 0.5
        for slot in TICKS:
            for pose in self.frames(slot):
                p = [list(r) for r in pose]
                p[0] = [4096] * 3 + [0] * 6
                w = mmd.bone_matrices(self.new, p)
                got = sum((w[16][i][3] - w[21][i][3]) ** 2 for i in range(3)) ** 0.5
                self.assertLess(abs(got - want), 3, slot)

    def test_the_legs_stay_attached_under_the_skirt(self):
        """The thigh stubs keep their rest place under the skirt (a few units of slide at most) and the mesh of each stub
        stays within a few units of the skirt's own footprint: the legs never come out of the body."""
        rest = self.frames(0)[0]
        for slot in TICKS:
            for pose in self.frames(slot):
                for bone in (6, 9):
                    for i, limit in enumerate((3, 4, 11)):
                        self.assertLessEqual(abs(pose[bone][6 + i] - rest[bone][6 + i]), limit, (slot, bone, i))
        skirt = [v[:3] for v in self.new.tmd.obj_verts(mmd.exe().skeleton[351][2][0])]
        lo = [min(v[i] for v in skirt) for i in range(3)]
        hi = [max(v[i] for v in skirt) for i in range(3)]
        verts = {b: [v[:3] for v in self.new.tmd.obj_verts(mmd.exe().skeleton[351][b][0])] for b in (6, 9)}
        for slot in TICKS:
            for pose in self.frames(slot)[:-1]:
                p = [list(r) for r in pose]
                p[0] = [4096] * 3 + [0] * 6
                w = mmd.bone_matrices(self.new, p)
                s = w[2]
                for bone, vs in verts.items():
                    for v in vs:
                        point = [sum(w[bone][i][j] * v[j] for j in range(3)) + w[bone][i][3] - s[i][3] for i in range(3)]
                        local = [sum(s[i][j] * point[i] for i in range(3)) for j in range(3)]
                        out = max(max(lo[k] - local[k], local[k] - hi[k], 0) for k in (0, 2))
                        self.assertLess(out, 12, (slot, bone))

    def test_each_foot_strides_and_the_two_stay_on_their_sides(self):
        for slot in TICKS:
            xs = {8: [], 11: []}
            for pose in self.frames(slot)[:-1]:
                p = [list(r) for r in pose]
                p[0] = [4096] * 3 + [0] * 6
                w = mmd.bone_matrices(self.new, p)
                for b in xs:
                    xs[b].append(w[b][0][3])
            self.assertGreater(min(xs[8]), 20, slot)
            self.assertLess(max(xs[11]), -20, slot)

    def test_the_walk_and_run_bounce_and_the_tired_walk_bounces_less(self):
        """The skirt (2) and the head (17) rise and fall on the beat: walk and run clearly, the tired walk less, the run most.
        The hop is a spring of the upper body, so it is a smooth arc and the jump test below does not see it as a glitch."""
        rng = {}
        for slot in TICKS:
            ys = {2: [], 17: []}
            for pose in self.frames(slot):
                p = [list(r) for r in pose]
                p[0] = [4096] * 3 + [0] * 6
                w = mmd.bone_matrices(self.new, p)
                for b in ys:
                    ys[b].append(-w[b][1][3])
            rng[slot] = {b: max(v) - min(v) for b, v in ys.items()}
            steps = [abs(a - b) for a, b in zip(ys[2], ys[2][1:])]
            self.assertLess(max(steps), 2.5 * sorted(steps)[len(steps) // 2] + 2, slot)
        self.assertGreater(rng[2][2], 8)
        self.assertGreater(rng[4][2], 11)
        self.assertGreater(rng[3][2], 4)
        self.assertLess(rng[3][2], rng[2][2])
        self.assertLess(rng[2][2], rng[4][2])
        self.assertGreater(rng[2][17], 4.5)


if __name__ == '__main__':
    unittest.main()
