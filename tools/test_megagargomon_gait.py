"""Check MegaGargomon's idle, walk, tired walk and run (species 335) on the real import.

MEGAGARGOMON_MODEL names the model the field overlay receives (the imported model with its equipment, before the chibi
proportions): `megagargomon_gait.build` runs on it (a few seconds) and the result is checked. Without it the test skips.

MegaGargomon faces -z: upper body 1, hips 2, left leg 3-6 (thigh, shin, ankle, toes), right leg 8-11, hip flaps 7 and 12,
shoulder cannons 13 (right) and 23 (left), arms 14-16 and 24-26, head 17, face plate 18, head fins 19 and 22.
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
from tools.models.field_animations import megagargomon_gait as gait

BONES = 27
TICKS = {2: 40, 3: 48, 4: 40}               # each clip is two different cycles of 20, 24 and 20 ticks
IDLE_TICKS = 80
SPEED = {2: 17, 3: 11, 4: 36}
TOES = {'LH': 6, 'RH': 11}


class MegaGargomonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        env = os.environ.get('MEGAGARGOMON_MODEL')
        if not env or not Path(env).exists():
            raise unittest.SkipTest('set MEGAGARGOMON_MODEL to the overlay input (species_model of 335)')
        cls.rig = json.loads(Path('content/species/335-megagargomon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[335] = cls.rig
        mmd.exe().bone_count[335] = BONES
        cls.data, cls.report = gait.build(Path(env).read_bytes(), cls.rig)
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 335
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        np = self.np
        rows = []
        for pose in self.frames(slot):
            mats = self.world(pose)
            rows.append({n: tuple(float(np.array(mats[b], float)[i, 3]) * (1, -1, 1)[i] for i in range(3)) for n, b in TOES.items()})
            for n in rows[-1]:
                x, y, z = rows[-1][n]
                rows[-1][n] = (x, y - pose[0][7], z + pose[0][8])
        return rows

    def test_chibi_proportions_and_the_record_patch_are_kept(self):
        self.assertIn('species_patch', self.report)
        self.assertEqual(self.report['gait']['changed_slots'], [0, 1, 2, 3, 4, 18, 33])

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))
        for b, least in ((17, 10), (1, 10), (14, 20)):          # head, upper body, an arm all move
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

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
        import animstudio, tempfile
        d = tempfile.mkdtemp()
        Path(d, 'm.MMD').write_bytes(self.data)
        tim = Path(os.environ['MEGAGARGOMON_MODEL']).with_suffix('.TIM')
        if not tim.exists():
            self.skipTest('the .TIM next to the model is missing')
        Path(d, 'm.TIM').write_bytes(tim.read_bytes())
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{d}/m.MMD:335:{d}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def test_the_feet_clear_the_floor_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_the_gaits_differ_and_the_two_cycles_are_not_alike(self):
        for slot, ticks in TICKS.items():
            half = ticks // 2
            frames = self.frames(slot)
            for b, least in ((1, 6), (3, 6), (8, 6), (14, 6), (17, 2)):
                gap = max(max(abs(frames[i][b][k] - frames[i + half][b][k]) for k in (3, 4, 5)) for i in range(half))
                self.assertGreater(gap, least, (slot, b))
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_whole_body_moves_not_only_the_legs(self):
        """The old clips turned the legs and upper arms only: torso, hips, cannons, forearms, fists and head stayed put."""
        for slot, least in ((2, 20), (3, 14), (4, 25)):
            frames = self.frames(slot)[:-1]
            for b in (1, 2, 13, 23, 15, 25, 17):
                spread = max(max(f[b][i] for f in frames) - min(f[b][i] for f in frames) for i in (3, 4, 5))
                self.assertGreater(min(spread, 4096 - spread), least, (slot, b))

    def test_no_tick_jumps(self):
        np, mesh = self.np, self.mesh
        for slot in (0, *TICKS):
            speeds, prev = [], None
            for pose in self.frames(slot):
                world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * med, slot)


if __name__ == '__main__':
    unittest.main()
