"""Check Gallantmon's idle, walk, tired walk and run (species 318) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 318`; GALLANTMON_MODEL names another
path). Before the change it is `gallantmon_gait.SOURCE`: the generator is run on it and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.

Gallantmon faces -z: upper body 1, right arm 2-4 (the lance in the hand) with its pauldron 5, head 6 with the plume
7-11, left arm 12-14 (the shield in the hand) with its pauldron 15, cape 16-18, pelvis 19, right leg 20-23 (thigh, shin,
ankle, toes), left leg 24-27.
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
from tools.models.field_animations import gallantmon_gait as gait, quadruped
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = '873883c3e9fe8b7ea69b6ad2c1050891e7576ef707b92278b42ccc3230f7f585'
BONES = 28
TICKS = {2: 24, 3: 30, 4: 18}
IDLE_TICKS = 120
HEAD = 6
SPEED = {2: 16, 3: 11, 4: 38}
LEGS = {'LH': (24, 25, 26, 27), 'RH': (20, 21, 22, 23)}          # hip, knee, heel, toes
TOES = {'LH': 27, 'RH': 23}
LEFT_LEG, RIGHT_LEG = [24, 25, 26, 27], [20, 21, 22, 23]
ARMS = [2, 3, 5, 12, 13, 15]
CAPE = [16, 17, 18]
SHIELD, LANCE, PELVIS = [14], [4], 19
# vertices and triangle centres inside another part, worst sampled tick per slot: the imported clips had the thighs in
# the pelvis 23 / 24 / 47 times (walk, tired walk, run) and the arms in the body 5; the shield and the lance never touched
# the legs. The rest pose already overlaps a little (idle 8-9).
LEGS_IN_PELVIS = {2: 23, 3: 24, 4: 47}
ARMS_IN_BODY = 5
SHIELD_IN_LEGS = 0
CAPE_IN_BODY = 8


class GallantmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('GALLANTMON_MODEL', 'build/imported-model-edit/edit/318-Gallantmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 318')
        cls.rig = json.loads(Path('content/species/318-gallantmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[318] = cls.rig
        mmd.exe().bone_count[318] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 318
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 318
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

    def floor_of(self, slot, name):
        """The toe point's height when the sole lies flat: the toe origin sits about 25 units above the floor, so a stance
        is judged against the lowest the same foot reaches in the clip."""
        return min(r[name][1] for r in self.feet(slot))

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
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4, 33, 35, 36])      # the idle is redone too (it was the model's own); slot 33 plays it as well
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
        for b, least in ((HEAD, 20), (1, 20), (4, 20), (17, 20)):             # head, upper body, the lance hand, the cape
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
                stance = [i for i, r in enumerate(rows) if r[name][1] < self.floor_of(slot, name) + 8]
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
            spec = f'{self._write()}:318:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            src = Path(os.environ.get('GALLANTMON_MODEL', 'build/imported-model-edit/edit/318-Gallantmon.MMD')).with_suffix('.TIM')
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
        least = {2: 14, 3: 14, 4: 19}           # the pelvis' height, peak to peak (the clips before this had 10 / 10 / 13)
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)
            n = len(height)
            smooth = [sum(height[(i + k) % n] for k in (-1, 0, 1)) / 3 for i in range(n)]
            peaks = [i for i in range(n) if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[(i + 1) % n]]
            self.assertEqual(len(peaks), 2, (slot, peaks))       # one dip per step

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
                    self.assertLess(dist, upper + lower - 1, (slot, leg, tick))
                    self.assertGreater(dist, abs(upper - lower) + 5, (slot, leg, tick))

    def test_penetration_is_no_worse_than_before(self):
        for slot in TICKS:
            self.assertLessEqual(self.worst_inside(slot, LEFT_LEG + RIGHT_LEG, [PELVIS]), LEGS_IN_PELVIS[slot], slot)
            self.assertLessEqual(self.worst_inside(slot, SHIELD + LANCE, [PELVIS] + LEFT_LEG + RIGHT_LEG), SHIELD_IN_LEGS, slot)
            self.assertEqual(self.worst_inside(slot, LEFT_LEG, RIGHT_LEG), 0, slot)
            self.assertEqual(self.worst_inside(slot, RIGHT_LEG, LEFT_LEG), 0, slot)
        for slot in (0, *TICKS):
            for arm in ([2, 3, 5], [12, 13, 15]):
                self.assertLessEqual(self.worst_inside(slot, arm, [1, 6]), ARMS_IN_BODY, slot)
            self.assertLessEqual(self.worst_inside(slot, CAPE, [1, PELVIS] + ARMS + LEFT_LEG + RIGHT_LEG), CAPE_IN_BODY, slot)

    def test_nothing_goes_through_the_floor(self):
        np, mesh = self.np, self.mesh
        for slot in (0, *TICKS):
            for pose in self.frames(slot)[:-1]:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float).reshape(-1, 3)
                self.assertGreater(-float(world[:, 1].max()) - pose[0][7], -6, slot)      # the lowest vertex, floor at 0

    def test_battle_slots_play_the_field_clips(self):
        for twin, slot in ((33, 0), (35, 2), (36, 4)):
            self.assertEqual(self.new.anims.table[twin], self.new.anims.table[slot], twin)


if __name__ == '__main__':
    unittest.main()
