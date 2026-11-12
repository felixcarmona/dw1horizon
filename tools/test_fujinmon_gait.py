"""Check Fujinmon's walk, tired walk and run (species 317) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 317`; FUJINMON_MODEL names another
path). Before the change it is `fujinmon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself and the checks that need the old clips are skipped.

Fujinmon faces -z: body 1, chest 2, right arm 3-6, left arm 7-10, head 11, scarf 12-15, pelvis 16, left leg 17-20 (thigh,
shin, ankle, toes), right leg 21-24.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import fujinmon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = '7d93b256ceb7ea25399d779cd7b5ca700769441e837ad059e0403edd09a8442a'
BONES = 25
TICKS = {2: 20, 3: 28, 4: 14}
SPEED = {2: 18, 3: 12, 4: 40}
TOES = {'LH': 20, 'RH': 24}
LEFT_LEG, RIGHT_LEG = [17, 18, 19, 20], [21, 22, 23, 24]
ARMS = [3, 4, 5, 6, 7, 8, 9, 10]
# vertices and triangle centres inside another part, worst sampled tick (the idle itself has 82 / 75; the clips before
# had 87 / 74, 83 / 74 and 87 / 89 in the legs-in-pelvis and arms-in-body counts)
LEGS_IN_HIPS = 80
ARMS_IN_BODY = 74


class FujinmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('FUJINMON_MODEL', 'build/imported-model-edit/edit/317-Fujinmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 317')
        cls.tim = path.with_suffix('.TIM')
        cls.rig = json.loads(Path('content/species/317-fujinmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[317] = cls.rig
        mmd.exe().bone_count[317] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 317
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 317
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        np = self.np
        rows = []
        for pose in self.frames(slot):
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            mats = mmd.bone_matrices(self.new, p)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def worst_inside(self, slot, a_bones, b_bones):
        np, mesh = self.np, self.mesh
        worst = 0
        for pose in self.frames(slot)[:-1]:
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
            tri = world[mesh.tri[np.isin(mesh.bone, a_bones)]]
            points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
            tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
            votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
            worst = max(worst, int((votes >= 3).sum()))
        return worst

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_gaits_and_their_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), self.report['changed_slots'])
        self.assertEqual(changed_programs(self.old, self.new), [2, 3, 4, 36])     # 36 plays the run in battle
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(self.frames(0, self.old), self.frames(0))                 # the idle is the model's own

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)                         # whole ticks
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)
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

    def test_the_studio_measures_no_slide_in_stance(self):
        """A foot in the lowest quarter of its lift moves over the ground by under 25 % of the body's speed on average
        and 45 % at worst (the clips before: 44 / 120 / 83 % on average and up to 460 % at worst)."""
        import animstudio
        d = tempfile.mkdtemp()
        Path(d, 'm.MMD').write_bytes(self.data)
        Path(d, 'm.TIM').write_bytes(self.tim.read_bytes())
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{d}/m.MMD:317:{d}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 15, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def test_each_foot_strides_fore_and_aft_and_the_feet_stay_apart(self):
        bounds = {2: 150, 3: 120, 4: 200}          # fore-aft travel of a toe in the body frame (units)
        for slot in TICKS:
            rows = self.feet(slot)[:-1]
            speed = SPEED[slot]
            for name, side in (('LH', -1), ('RH', 1)):
                self.assertGreater(min(r[name][0] * side for r in rows), 20, (slot, name))
            for name in TOES:
                body = [r[name][2] + speed * i for i, r in enumerate(rows)]
                self.assertGreater(max(body) - min(body), bounds[slot], (slot, name))

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            for name in TOES:
                heights = [r[name][1] for r in self.feet(slot)]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 20, (slot, name))

    def test_the_run_has_a_flight_phase_and_leans_forward(self):
        rows = self.feet(4)[:-1]
        flight = [i for i, r in enumerate(rows) if min(r[n][1] for n in TOES) > 12]
        self.assertGreaterEqual(len(flight), 2)                  # both soles off the floor for whole ticks
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)[:-1]) / TICKS[slot]
        self.assertGreater(mean(4, 3), mean(2, 3) + 80)          # the body pitch, 4096 to a turn: 10 degrees and more
        self.assertGreater(mean(3, 7), mean(2, 7))               # the tired walk rides lower (y grows downward)

    def test_the_body_sinks_and_rises_twice_a_cycle(self):
        least = {2: 8, 3: 8, 4: 14}
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)
            self.assertLessEqual(max(height) - min(height), 30, slot)

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

    def test_no_bone_turns_more_than_70_degrees_in_a_tick(self):
        """The imported run turned a limb up to 50 degrees a tick; the longest step here is the lift-off of a run (58)."""
        for slot in TICKS:
            frames = self.frames(slot)
            for tick in range(len(frames) - 1):
                for b in range(1, BONES):
                    a = [mmd.quat(*frames[tick][b][3:6]), mmd.quat(*frames[tick + 1][b][3:6])]
                    dot = min(1.0, abs(sum(x * y for x, y in zip(*a))))
                    self.assertLess(math.degrees(2 * math.acos(dot)), 70, (slot, tick, b))

    def test_the_pauldron_rotors_turn_one_whole_turn_a_loop_about_their_axle(self):
        """The spiked pauldrons (bones 6 and 10, parented to the chest) are rotors that spin about the local x axle, as in
        the model's own idle and run; one turn a loop closes it, and the rate follows the loop: walk 18, tired 13, run 26
        degrees a tick (the model's own run turned them 22, its walk and tired walk not a whole turn)."""
        rates = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            for bone in (6, 10):
                steps = [(frames[i + 1][bone][3] - frames[i][bone][3]) % 4096 for i in range(ticks)]
                self.assertEqual(sum(steps), 4096, (slot, bone))                       # one whole turn
                self.assertLessEqual(max(steps) - min(steps), 1, (slot, bone))          # even, no stutter
                self.assertTrue(all(0 < x <= 4096 * 30 // 360 for x in steps), (slot, bone))   # under 30 degrees: no strobing
                for tick in range(ticks + 1):
                    self.assertEqual(frames[tick][bone][4:6], [0, 0], (slot, bone, tick))      # about the axle only
            rates[slot] = steps[0] * 360 / 4096
        self.assertLess(rates[3], rates[2])
        self.assertLess(rates[2], rates[4])
        self.assertGreater(rates[3], 10)
        self.assertLess(rates[4], 30)
        self.assertEqual(self.frames(36), self.frames(4))                                # the battle run turns them too

    def test_arms_and_legs_do_not_penetrate_more_than_before(self):
        for slot in TICKS:
            self.assertEqual(self.worst_inside(slot, ARMS, LEFT_LEG + RIGHT_LEG), 0, slot)
            self.assertEqual(self.worst_inside(slot, LEFT_LEG, RIGHT_LEG) + self.worst_inside(slot, RIGHT_LEG, LEFT_LEG), 0, slot)
            self.assertLessEqual(self.worst_inside(slot, LEFT_LEG + RIGHT_LEG, [16]), LEGS_IN_HIPS, slot)
            self.assertLessEqual(self.worst_inside(slot, ARMS, [1, 2]), ARMS_IN_BODY, slot)


if __name__ == '__main__':
    unittest.main()
