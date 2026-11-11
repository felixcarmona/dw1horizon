"""Check Marsmon's idle, walk, tired walk and run (species 297) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 297`; MARSMON_MODEL names another
path). Before the change it is `marsmon_gait.PROFILE['source']`: the generator is run on it and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.

Marsmon faces -z: upper body 1, right arm 2-4, left arm 5-7, head 8, cape 9-11, hips 12, left leg 13-16 (hip, knee,
heel, toes), right leg 17-20.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import marsmon_gait as gait, quadruped
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = 'f1f71a0a658fb25de575f874585ed0483b39cd55632feb579b25200011692a61'
BONES = 21
TICKS = {2: 22, 3: 26, 4: 14}
IDLE_TICKS = 150
HEAD = 8
SPEED = {2: 16, 3: 11, 4: 38}
LEGS = {'LH': (13, 14, 15, 16), 'RH': (17, 18, 19, 20)}          # hip, knee, heel, toes
TOES = {'LH': 16, 'RH': 20}
LEFT_LEG, RIGHT_LEG = [13, 14, 15, 16], [17, 18, 19, 20]
ARMS = [2, 3, 4, 5, 6, 7]
CAPE = [9, 10, 11]
# vertices and triangle centres inside another part, worst sampled tick per slot: the imported clips had the arms in the
# hips and legs 14 / 93 / 13 times and each leg in the other 102-183 times; the hips (bone 12) hold the leg tops (34-38)
ARMS_IN_LEGS = {2: 0, 3: 0, 4: 0}
LEGS_IN_LEGS = {2: 22, 3: 24, 4: 22}
LEGS_IN_HIPS = 45
CAPE_IN_BODY = 24            # the cape's rest pose already overlaps the body this much; no clip makes it worse


class MarsmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('MARSMON_MODEL', 'build/imported-model-edit/edit/297-Marsmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 297')
        cls.rig = json.loads(Path('content/species/297-marsmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[297] = cls.rig
        mmd.exe().bone_count[297] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 297
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 297
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._feet = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot, model=None):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        np = self.np
        model = model or self.new
        rows = []
        for pose in self.frames(slot, model):
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            mats = mmd.bone_matrices(model, p)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def inside_count(self, pose, a_bones, b_bones, model=None):
        np, mesh = self.np, self.mesh
        model = model or self.new
        if model is not self.new:
            import animstudio
            mesh = animstudio.FastMesh(SimpleNamespace(m=model, skel=self.rig))
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        world = mesh.world(mmd.bone_matrices(model, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def worst_inside(self, slot, a_bones, b_bones, model=None):
        frames = self.frames(slot, model)
        return max(self.inside_count(f, a_bones, b_bones, model) for f in frames[:-1])

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_their_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), self.report['changed_slots'])
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4, 33])      # the idle is redone too (it was the model's own); slot 33 plays it as well
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})                 # no travel
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))
        rows = self.feet(0)
        for name in TOES:
            for axis in (0, 2):
                values = [r[name][axis] for r in rows]
                self.assertLess(max(values) - min(values), 4, (name, axis))      # both boots stay where they are
            heights = [r[name][1] for r in rows]
            self.assertLess(max(heights) - min(heights), 4, name)            # the sole stays flat on the floor

    def test_the_idle_moves_with_character_and_without_jumps(self):
        np, mesh = self.np, self.mesh
        frames = self.frames(0)
        for b, least in ((HEAD, 20), (1, 20), (4, 40), (10, 20)):             # head, upper body, a fist, the cape
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)
        speeds, prev = [], None
        for pose in frames:
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float).reshape(-1, 3)
            if prev is not None:
                speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
            prev = world
        # the clip is stored in whole units, so a slow move steps by one unit now and then: judge the speed over 5 ticks
        wide = [sum(speeds[(i + k) % len(speeds)] for k in range(-2, 3)) / 5 for i in range(len(speeds))]
        med = sorted(speeds)[len(speeds) // 2]
        self.assertLess(max(wide), 2.5 * med)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)                # the same step every tick
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)
        self.assertGreater(TICKS[3], TICKS[2])

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_feet_are_planted_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                stance = [i for i, r in enumerate(rows) if r[name][1] < 24]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_studio_measures_no_slide_in_stance(self):
        """The studio's own measure: a foot in the lowest quarter of its lift moves over the ground by under 25 % of the
        body's speed on average and 45 % at worst (the imported clips: up to 88 % on average and 449 % at worst)."""
        import animstudio
        for slot in TICKS:
            spec = f'{self._write()}:297:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 15, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            src = Path(os.environ.get('MARSMON_MODEL', 'build/imported-model-edit/edit/297-Marsmon.MMD')).with_suffix('.TIM')
            Path(self._dir, 'm.TIM').write_bytes(src.read_bytes())
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))

    def test_each_foot_strides_fore_and_aft_and_the_two_stay_apart(self):
        """The imported clips put both soles on the left side (the right one crossed to x = -17); now the feet stay on
        their own sides of the body, 80 units and more apart, and each takes a long step."""
        bounds = {2: 120, 3: 100, 4: 100}          # fore-aft travel of a toe in the body frame (units)
        for slot in TICKS:
            rows = self.feet(slot)[:-1]
            speed = SPEED[slot]
            for name, side in (('LH', -1), ('RH', 1)):
                xs = [r[name][0] for r in rows]
                self.assertGreater(min(x * side for x in xs), 20, (slot, name))      # never across the middle
            sep = [abs(r['RH'][0] - r['LH'][0]) for r in rows]
            self.assertGreater(min(sep), 70, slot)
            for name in TOES:
                body = [r[name][2] + speed * i for i, r in enumerate(rows)]        # back to the body frame
                self.assertGreater(max(body) - min(body), bounds[slot], (slot, name))
            ahead = [(r['LH'][2] + speed * i) - (r['RH'][2] + speed * i) for i, r in enumerate(rows)]
            self.assertGreater(max(ahead), 60, slot)                               # each leads in turn
            self.assertLess(min(ahead), -60, slot)

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_the_tired_walk_rides_lower_and_leans_further_and_the_run_leans_most(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3, 7), mean(2, 7))              # y grows downward
        self.assertGreater(mean(3, 3), mean(2, 3))
        self.assertGreater(mean(4, 3), mean(3, 3))
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_body_sinks_and_rises_twice_a_cycle_by_a_clear_amount(self):
        least = {2: 14, 3: 16, 4: 19}           # the pelvis' height, peak to peak (the clips before this had 10 / 10 / 13)
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)
            n = len(height)
            smooth = [sum(height[(i + k) % n] for k in (-1, 0, 1)) / 3 for i in range(n)]
            peaks = [i for i in range(n) if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[(i + 1) % n]]
            self.assertEqual(len(peaks), 2, (slot, peaks))       # one dip per step

    def test_each_boot_points_along_the_way_and_never_flicks_up_or_back(self):
        """The toe stays within a few degrees of its own splay (30 degrees outward) round the whole loop, the toe never
        rises above the heel's level beyond a few degrees (the run before had it turning to -3 as the foot left the ground)
        and the shin never swings far past horizontal (the heel kicked up behind; the run before had it at 93-95 with the heel 116 high)."""
        np = self.np
        for slot in TICKS:
            last = {}
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                pts = [np.array(m, float)[:3, 3] for m in mmd.bone_matrices(self.new, p)]
                for leg, (hip, knee, heel, toe) in LEGS.items():
                    d = pts[toe] - pts[heel]
                    yaw = math.degrees(math.atan2(d[0], -d[2]))
                    side = 1 if leg == 'RH' else -1
                    self.assertLess(abs(yaw - 30 * side), 6, (slot, leg, tick))
                    pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
                    self.assertGreater(pitch, 8, (slot, leg, tick))
                    shin = pts[heel] - pts[knee]
                    self.assertLess(math.degrees(math.atan2(shin[2], shin[1])), 95, (slot, leg, tick))

    def test_no_tick_jumps(self):
        np, mesh = self.np, self.mesh
        for slot in TICKS:
            speeds, prev = [], None
            for pose in self.frames(slot):
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        np = self.np
        norm = np.linalg.norm
        for slot in TICKS:
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                pts = [np.array(m, float)[:3, 3] for m in mmd.bone_matrices(self.new, p)]
                for leg, (hip, knee, heel, _) in LEGS.items():
                    upper, lower, dist = norm(pts[knee] - pts[hip]), norm(pts[heel] - pts[knee]), norm(pts[heel] - pts[hip])
                    self.assertLess(dist, upper + lower - 3, (slot, leg, tick))
                    self.assertGreater(dist, abs(upper - lower) + 5, (slot, leg, tick))

    def test_arms_and_legs_penetrate_far_less_than_before(self):
        for slot in TICKS:
            self.assertLessEqual(self.worst_inside(slot, ARMS, [12] + LEFT_LEG + RIGHT_LEG), ARMS_IN_LEGS[slot], slot)
            self.assertLessEqual(self.worst_inside(slot, LEFT_LEG, RIGHT_LEG), LEGS_IN_LEGS[slot], slot)
            self.assertLessEqual(self.worst_inside(slot, RIGHT_LEG, LEFT_LEG), LEGS_IN_LEGS[slot], slot)
            self.assertLessEqual(self.worst_inside(slot, LEFT_LEG + RIGHT_LEG, [12]), LEGS_IN_HIPS, slot)
        for slot in (0, *TICKS):
            self.assertLessEqual(self.worst_inside(slot, CAPE, [1, 12] + ARMS + LEFT_LEG + RIGHT_LEG), CAPE_IN_BODY, slot)


if __name__ == '__main__':
    unittest.main()
