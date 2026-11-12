"""Check Pharaohmon's tired walk and run (species 319) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 319`; PHARAOHMON_MODEL names another
path). The test runs `pharaohmon_gait.build` on it and checks the result against the celebrations build it starts from.

Pharaohmon faces -z: torso 1, head 5, cape 6-7, hips 11, loincloth 16-17, arms 2-3-4 (x < 0) and 8-9-10, right leg 12-15
(thigh, shin, ankle block, claws), left leg 18-21.
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
from tools.models.field_animations import celebrations, pharaohmon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

BONES = 22
TICKS = {3: 56, 4: 24}               # each clip is two different cycles of 28 and 12 ticks
SPEED = {3: 11, 4: 36}
WALK_SPEED = 19.5                    # the walk (slot 2) is the celebrations build's, untouched
TOES = {'LH': 21, 'RH': 15}
LEGS = {'LH': (18, 19, 20, 21), 'RH': (12, 13, 14, 15)}
G = dict(arm_r=[8, 9, 10], arm_l=[2, 3, 4], leg_r=[12, 13, 14, 15], leg_l=[18, 19, 20, 21], hips=[11], torso=[1],
         cape=[6, 7], cloth=[16, 17])
PAIRS = [('arm_r', 'torso'), ('arm_l', 'torso'), ('arm_r', 'leg_r'), ('arm_r', 'leg_l'), ('arm_l', 'leg_r'),
         ('arm_l', 'leg_l'), ('arm_r', 'hips'), ('arm_l', 'hips'), ('leg_r', 'leg_l'), ('leg_l', 'leg_r'),
         ('cloth', 'leg_r'), ('cloth', 'leg_l'), ('arm_r', 'cloth'), ('arm_l', 'cloth')]


class PharaohmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('PHARAOHMON_MODEL', 'build/imported-model-edit/edit/319-Pharaohmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 319')
        cls.path = path
        cls.rig = json.loads(Path('content/species/319-pharaohmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[319] = cls.rig
        mmd.exe().bone_count[319] = BONES
        base, _ = celebrations.build(path.read_bytes(), cls.rig)
        cls.data, cls.report = gait.build(path.read_bytes(), cls.rig)
        cls.old = mmd.MMD.parse(base, BONES)
        cls.old.type = 319
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 319
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls.mesh_old = animstudio.FastMesh(SimpleNamespace(m=cls.old, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def world(self, pose, model=None):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(model or self.new, p)

    def lean(self, pose):
        """The head over the hips, degrees from vertical (positive: forward, -z)."""
        import math
        m = self.world(pose)
        head, hips = (self.np.array(m[b], float)[:3, 3] for b in (5, 11))
        return math.degrees(math.atan2(hips[2] - head[2], hips[1] - head[1]))

    def feet(self, slot):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        rows = []
        for pose in self.frames(slot):
            mats = self.world(pose)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(self.np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def test_only_the_tired_walk_and_the_run_change_and_the_idle_and_walk_stay_byte_identical(self):
        self.assertEqual(self.report['gait']['changed_slots'], [3, 4])
        for slot in range(len(self.old.anims.table)):
            if slot in (3, 4):
                continue
            a, b = self.old.anims.table[slot], self.new.anims.table[slot]
            self.assertEqual(a is None, b is None, slot)
            if a is not None:
                self.assertEqual(self.old.anims.anims[a].build(), self.new.anims.anims[b].build(), slot)
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

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
            self.assertEqual(len(steps), 1, slot)                # the same step every tick
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        walk = self.frames(2)
        walk_speed = -(walk[-1][0][8] - walk[0][0][8]) / (len(walk) - 1)
        self.assertAlmostEqual(walk_speed, WALK_SPEED, delta=0.6)
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
        """The studio's measure: a foot in the lowest quarter of its lift moves over the ground by under 25 % of the
        body's speed on average and 45 % at worst (the old tired walk: 138 % mean, 466 % worst)."""
        import animstudio
        for slot in TICKS:
            studio = animstudio.Model(f'{self._write()}:319:{self._write(tim=True)}', slot)
            _, results = animstudio.metrics(studio)
            for bone, stance, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 22 if slot == 3 else 30, (slot, bone))
                self.assertGreaterEqual(stance, 3, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            Path(self._dir, 'm.TIM').write_bytes(self.path.with_suffix('.TIM').read_bytes())
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))

    def test_the_sole_stays_put_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                stance = [i for i, r in enumerate(rows) if r[name][1] < 56]
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance and rows[i][name][1] < 54]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), 46, (slot, name))     # the claw point rests 52 over the floor
                self.assertGreater(max(heights) - min(heights), 22 if slot == 3 else 30, (slot, name))

    def test_the_tired_foot_lifts_low_round_and_without_a_pop(self):
        """The v1 tired walk popped each toe up 62 units in 5 ticks with the toe tipped up 30 degrees (a kick). Now the
        toe rises 25 to 32 units over about 8 ticks, never more than 8 in a tick, stays rounded (second difference
        under 7) and never rises above the ankle by more than the foot's own pitch allows."""
        rows = self.feet(3)[:-1]
        for name in TOES:
            h = [r[name][1] for r in rows]
            n = len(h)
            rest = min(h)
            self.assertLess(max(h) - rest, 36, name)
            self.assertGreater(max(h) - rest, 22, name)
            step = [h[(i + 1) % n] - h[i] for i in range(n)]
            self.assertLess(max(abs(d) for d in step), 8, name)
            self.assertLess(max(abs(step[(i + 1) % n] - step[i]) for i in range(n)), 7, name)
            risen = [i for i in range(n) if h[i] > rest + 4]          # the foot is off the floor about 18 of 28 ticks
            self.assertGreater(len(risen), 26, name)
            self.assertLess(len(risen), 40, name)
        pitch = []
        for pose in self.frames(3)[:-1]:
            m = self.world(pose)
            toe, ankle = (self.np.array(m[b], float)[:3, 3] for b in (21, 20))
            pitch.append(float(ankle[1] - toe[1]) * -1)               # ankle height over the toe's, world units
        self.assertGreater(min(pitch), 12)                            # the toe never rises to the ankle (v1: 0 to -6)

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
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_the_torso_leans_a_controlled_amount_in_every_tick(self):
        """The old tired walk leant 16 to 37 degrees past the idle's -12 and the run 48 to 58: a bent statue. The walk
        (untouched) is 0 to 17."""
        walk = [self.lean(f) for f in self.frames(2)[:-1]]
        tired = [self.lean(f) for f in self.frames(3)[:-1]]
        run = [self.lean(f) for f in self.frames(4)[:-1]]
        self.assertGreater(min(tired), 0)
        self.assertLess(max(tired), 22)
        self.assertGreater(sum(run) / len(run), sum(tired) / len(tired))
        self.assertLess(max(run), 30)
        self.assertLess(max(walk), 20)
        for series in (tired, run):                    # no tick snaps the torso
            step = [abs(series[(i + 1) % len(series)] - series[i]) for i in range(len(series))]
            self.assertLess(max(step), 4, series)

    def test_the_body_sinks_and_rises_with_every_step(self):
        for slot, (least, most) in {3: (15, 45), 4: (15, 50)}.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), least, slot)
            self.assertLessEqual(max(height) - min(height), most, slot)

    def test_the_arms_swing_and_the_cape_trails(self):
        for slot, least in ((3, 8), (4, 25)):
            for b in (4, 10):
                zs = [float(self.np.array(self.world(f)[b], float)[2, 3]) for f in self.frames(slot)[:-1]]
                self.assertGreater(max(zs) - min(zs), least, (slot, b))
            turns = [f[7][3] for f in self.frames(slot)[:-1]]
            self.assertGreater(max(turns) - min(turns), 10, slot)

    def test_the_two_cycles_are_not_alike(self):
        for slot, ticks in TICKS.items():
            half = ticks // 2
            frames = self.frames(slot)
            for b, least in ((1, 3), (2, 3), (8, 3)):
                gap = max(max(abs(frames[i][b][k] - frames[i + half][b][k]) for k in (3, 4, 5)) for i in range(half))
                self.assertGreater(gap, least, (slot, b))

    def inside_count(self, mesh, model, pose, a, b):
        np = self.np
        world = mesh.world(self.world(pose, model)).astype(float)
        tri = world[mesh.tri[np.isin(mesh.bone, G[a])]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, G[b])]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_parts_penetrate_no_more_than_in_the_old_clips(self):
        for slot in TICKS:
            old, new = self.frames(slot, self.old)[:-1:2], self.frames(slot)[:-1:2]
            for a, b in PAIRS:
                before = max(self.inside_count(self.mesh_old, self.old, f, a, b) for f in old)
                after = max(self.inside_count(self.mesh, self.new, f, a, b) for f in new)
                slack = 10 if a == 'cloth' else 2          # the loincloth swings through a thigh a little more in the run (34 against 26)
                self.assertLessEqual(after, before + slack, (a, b, slot, before, after))


if __name__ == '__main__':
    unittest.main()
