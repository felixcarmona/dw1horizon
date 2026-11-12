"""Check Knightmon's tired walk and run (species 321) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 321`; KNIGHTMON_MODEL names another
path). The test runs `knightmon_gait.build` on it (chibi reshaping, then the two clips) and checks the result: the walk
and the idle are the chibi model's own, byte for byte; the tired walk is even left to right; both clips are smooth.

Knightmon faces -z: upper body 1, right arm 2-5, left arm 7-10 with the sword 11, head 6, cloak 12, hips 13, scabbard 14,
right leg 15-19 (thigh, knee guard, knee, foot, toe plate), loincloth 20-21, left leg 22-26.
"""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import knightmon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

BONES = 27
TICKS = {3: 22, 4: 16}
SPEED = {3: 11.5, 4: 38}
TOES = {'LH': 26, 'RH': 19}
G = dict(arm_r=[2, 3, 4, 5], arm_l=[7, 8, 9, 10, 11], leg_r=[15, 16, 17, 18, 19], leg_l=[22, 23, 24, 25, 26], torso=[1], hips=[13],
         head=[6], scab=[14])
# worst sampled tick of vertices and triangle centres inside another part. The previous clips measured (tired walk, run):
# arms in the legs 0 and 0 (left arm 0 / 62), scabbard in the right arm 2 / 0, head in the torso 47 / 105, legs in the torso
# 6 and 0 / 19 and 0, hips in the torso 27 / 22; the new clips stay within these (the plates of hips, legs and torso overlap
# in the rest pose already).
PENETRATION = {3: {('arm_r', 'leg_r'): 0, ('arm_l', 'leg_l'): 0, ('scab', 'arm_r'): 2, ('torso', 'head'): 52,
                   ('leg_r', 'torso'): 20, ('leg_l', 'torso'): 20, ('hips', 'torso'): 38},
               4: {('arm_r', 'leg_r'): 0, ('arm_l', 'leg_l'): 62, ('scab', 'arm_r'): 6, ('torso', 'head'): 105,
                   ('leg_r', 'torso'): 30, ('leg_l', 'torso'): 30, ('hips', 'torso'): 38}}


class KnightmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('KNIGHTMON_MODEL', 'build/imported-model-edit/edit/321-Knightmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 321')
        cls.rig = json.loads(Path('content/species/321-knightmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[321] = cls.rig
        mmd.exe().bone_count[321] = BONES
        from tools.models.field_animations import chibi
        cls.base, _ = chibi.build(path.read_bytes(), cls.rig)
        cls.data, cls.report = gait.build(path.read_bytes(), cls.rig)
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 321
        cls.old = mmd.MMD.parse(cls.base, BONES)
        cls.old.type = 321
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each toe plate's world position (x, height, z with the root's travel)."""
        np = self.np
        rows = []
        for pose in self.frames(slot):
            mats = self.world(pose)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def test_only_the_tired_walk_and_the_run_change(self):
        self.assertEqual(self.report['gait']['changed_slots'], [3, 4, 36])       # slot 36 plays the run as well
        for index, (a, b) in enumerate(zip(self.old.anims.anims, self.new.anims.anims)):
            same = a.build() == b.build()
            self.assertEqual(same, index not in (2, 3), index)                  # animations 2 (tired walk) and 3 (run)
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        walk = animsheet.slot_frames(self.new, BONES, 2)[0]
        walk_speed = -(walk[-1][0][8] - walk[0][0][8]) / (len(walk) - 1)
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertLessEqual(len(steps), 2, slot)           # the same step every tick (rounded to whole units)
            speeds[slot] = -(frames[-1][0][8] - frames[0][0][8]) / ticks
            self.assertAlmostEqual(speeds[slot], SPEED[slot], delta=0.5)
        self.assertLess(speeds[3], walk_speed)
        self.assertLess(walk_speed, speeds[4])
        self.assertTrue(10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_studio_measures_no_slide_in_stance(self):
        import animstudio
        import tempfile
        d = tempfile.mkdtemp()
        Path(d, 'm.MMD').write_bytes(self.data)
        src = Path(os.environ.get('KNIGHTMON_MODEL', 'build/imported-model-edit/edit/321-Knightmon.MMD')).with_suffix('.TIM')
        Path(d, 'm.TIM').write_bytes(src.read_bytes())
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{d}/m.MMD:321:{d}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def test_the_two_legs_walk_alike(self):
        """The tired walk is two mirrored strides: each foot's height, its stance and its lift match the other foot's half
        a cycle later (the previous clip stood one foot twice as long as the other and lifted 58 and 74 units)."""
        for slot in TICKS:
            rows = self.feet(slot)[:-1]
            n = len(rows)
            right = [r['RH'][1] for r in rows]
            left = [r['LH'][1] for r in rows]
            shifted = left[n // 2:] + left[:n // 2]
            span = max(right) - min(right)
            self.assertLess(max(abs(a - b) for a, b in zip(right, shifted)), 0.08 * span, slot)
            self.assertLess(abs(max(right) - max(left)), 0.05 * span, slot)
            stance = lambda h: sum(1 for v in h if v < 8)
            self.assertLessEqual(abs(stance(right) - stance(left)), 1, slot)
            # the fore-aft path in the body's frame repeats half a cycle later with the other foot
            body = {k: [r[k][2] + SPEED[slot] * i for i, r in enumerate(rows)] for k in TOES}
            back = body['LH'][n // 2:] + body['LH'][:n // 2]
            mean_r, mean_l = sum(body['RH']) / n, sum(back) / n
            reach = max(body['RH']) - min(body['RH'])
            self.assertLess(max(abs((a - mean_r) - (b - mean_l)) for a, b in zip(body['RH'], back)), 0.08 * reach, slot)

    def test_the_pelvis_dips_the_same_for_both_steps(self):
        for slot in TICKS:
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            n = len(height)
            half = n // 2
            gap = max(abs(height[i] - height[(i + half) % n]) for i in range(n))
            self.assertLessEqual(gap, 2, slot)

    def test_no_tick_jumps(self):
        np, mesh = self.np, self.mesh
        for slot in TICKS:
            speeds, prev = [], None
            for pose in self.frames(slot):
                world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.0 * med, slot)           # the previous clips: 2.5 times and more

    def test_every_channel_changes_smoothly(self):
        """No bone's turn jumps: its second difference stays a few times its median over the loop (before: 50-240)."""
        for slot in TICKS:
            frames = self.frames(slot)[:-1]
            for b in range(1, BONES):
                for ch in (3, 4, 5):
                    d = [(frames[(i + 1) % len(frames)][b][ch] - frames[i][b][ch] + 2048) % 4096 - 2048 for i in range(len(frames))]
                    acc = sorted(abs(d[(i + 1) % len(d)] - d[i]) for i in range(len(d)))
                    self.assertLess(acc[-1], 12 * (acc[len(acc) // 2] + 3), (slot, b, ch))

    def test_the_sword_does_not_whip(self):
        np = self.np
        for slot in TICKS:
            pitch = []
            for pose in self.frames(slot):
                m = np.array(self.world(pose)[11], float)
                pitch.append(float(np.degrees(np.arctan2(m[1, 2], np.hypot(m[0, 2], m[2, 2])))))
            self.assertLess(max(abs(b - a) for a, b in zip(pitch, pitch[1:])), 8, slot)
            self.assertLess(max(pitch) - min(pitch), 40, slot)

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 20, (slot, name))

    def test_the_run_rides_higher_in_motion_than_the_tired_walk(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(4, 3), mean(3, 3))                  # the run leans forward more

    def test_parts_penetrate_no_more_than_in_the_previous_clips(self):
        np, mesh = self.np, self.mesh
        for slot, pairs in PENETRATION.items():
            frames = self.frames(slot)[:-1]
            for (a, b), most in pairs.items():
                worst = 0
                for pose in frames:
                    world = mesh.world(self.world(pose)).astype(float)
                    tri = world[mesh.tri[np.isin(mesh.bone, G[a])]]
                    points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    tris = world[mesh.tri[np.isin(mesh.bone, G[b])]]
                    votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
                    worst = max(worst, int((votes >= 3).sum()))
                self.assertLessEqual(worst, most, (slot, a, b))


if __name__ == '__main__':
    unittest.main()
