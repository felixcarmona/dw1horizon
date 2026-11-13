"""Check WarGreymon's idle, walk, tired walk and run (species 373) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 373`; WARGREYMON_MODEL names another
path): the imported model, to which the overlay applies the chibi proportions and then these clips. The test runs
`wargreymon_gait.build` on it (a few seconds) and checks the result.

WarGreymon faces -z: pelvis 1, chest 2, neck 3, head 4, helmet 5, left arm 6-7, right arm 8-9, left leg 10-12, right leg
13-15, loincloth 16, thigh plates 17-18, back plates 19-20.
"""
import copy
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
from tools.models.field_animations import wargreymon_gait as gait

BONES = 21
TICKS = {2: 44, 3: 28, 4: 24}               # walk and run are two different cycles of 22 and 12 ticks; the tired walk is one of 28
IDLE_TICKS = 96
SPEED = {2: 16, 3: 10, 4: 40}
TOES = {'LH': 12, 'RH': 15}
G = dict(arm_l=[6, 7], arm_r=[8, 9], torso=[1, 2, 3], head=[4, 5], leg_l=[10, 11, 12], leg_r=[13, 14, 15], cloth=[16],
         tass_l=[17], tass_r=[18])
# triangles crossing another part, worst tick over the idle and the three gaits (meshclash). The chibi model's own
# clips measured: arms in the torso 20, the head in the chest 37 (the rest pose holds those), a thigh plate in its leg
# 63; the new clips stay within a few triangles of that and the arms and legs clear the head and the cloth better.
PENETRATION = {('arm_l', 'head'): 16, ('arm_r', 'head'): 14, ('arm_l', 'torso'): 22, ('arm_r', 'torso'): 22,
               ('leg_l', 'torso'): 25, ('leg_r', 'torso'): 27, ('tass_l', 'leg_l'): 64, ('tass_r', 'leg_r'): 65,
               ('torso', 'head'): 50, ('arm_l', 'tass_l'): 10, ('arm_r', 'tass_r'): 10, ('arm_r', 'leg_r'): 12}


class WarGreymonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('WARGREYMON_MODEL', 'build/imported-model-edit/edit/373-WarGreymon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 373')
        cls.rig = json.loads(Path('content/species/373-wargreymon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[373] = cls.rig
        mmd.exe().bone_count[373] = BONES
        cls.data, cls.report = gait.build(path.read_bytes(), cls.rig)
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 373
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each foot bone's world position (x, height, z with the root's travel)."""
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

    def test_chibi_proportions_and_the_record_patch_are_kept(self):
        self.assertIn('species_patch', self.report)
        self.assertEqual(self.report['gait']['changed_slots'], [0, 2, 3, 4, 33])    # slot 33 plays the idle as well

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
        rows = self.feet(0)
        for name in TOES:
            for axis in (0, 2):
                values = [r[name][axis] for r in rows]
                self.assertLess(max(values) - min(values), 4, (name, axis))
            heights = [r[name][1] for r in rows]
            self.assertLess(max(heights) - min(heights), 4, name)

    def test_the_idle_moves_with_character_and_without_jumps(self):
        np, mesh = self.np, self.mesh
        frames = self.frames(0)
        for b, least in ((4, 40), (2, 20), (9, 20), (19, 10)):             # head, chest, a claw, a back plate
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)
        speeds, prev = [], None
        for pose in frames:
            world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
            if prev is not None:
                speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
            prev = world
        wide = [sum(speeds[(i + k) % len(speeds)] for k in range(-2, 3)) / 5 for i in range(len(speeds))]
        med = sorted(speeds)[len(speeds) // 2]
        self.assertLess(max(wide), 2.5 * med)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)                # the same step every tick (before: 7 to 10 different steps)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)
        self.assertGreater(TICKS[3], TICKS[2] // 2)              # the tired cycle (28) is longer than the walk's (22)

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
        body's speed on average and 45 % at worst (the chibi clips before: tired walk 172 % mean, 446 % worst)."""
        import animstudio
        for slot in (0, *TICKS):
            spec = f'{self._write()}:373:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25 if slot else 5, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                if slot:
                    self.assertGreater(lift, 18, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            src = Path(os.environ.get('WARGREYMON_MODEL', 'build/imported-model-edit/edit/373-WarGreymon.MMD')).with_suffix('.TIM')
            Path(self._dir, 'm.TIM').write_bytes(src.read_bytes())
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))


    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights) - min(heights), 18, (slot, name))

    def test_the_gaits_differ_and_the_tired_walk_rides_lowest(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3, 7), mean(2, 7))              # y grows downward
        self.assertGreater(mean(3, 3), mean(2, 3))              # the tired walk leans (the pelvis pitch) deeper than the walk
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_two_cycles_and_the_two_legs_are_not_alike(self):
        """The metronome is broken: in the walk and the run the second half differs from the first."""
        for slot in (2, 4):
            half = TICKS[slot] // 2
            frames = self.frames(slot)
            for b, least in ((1, 6), (10, 6), (13, 6), (6, 3)):          # pelvis, the two thighs, an arm
                gap = max(max(abs(frames[i][b][k] - frames[i + half][b][k]) for k in (3, 4, 5)) for i in range(half))
                self.assertGreater(gap, least, (slot, b))

    def test_the_whole_body_moves_with_the_step(self):
        """Hips and chest counter-turn, the arms swing against the legs, the head and the back plates follow."""
        for slot, (hips, chest, arm, head, plate) in {2: (200, 400, 300, 150, 80), 3: (100, 250, 120, 80, 40),
                                                      4: (150, 300, 300, 100, 80)}.items():
            frames = self.frames(slot)[:-1]
            spread = lambda b, i: max(f[b][i] for f in frames) - min(f[b][i] for f in frames)
            self.assertGreater(spread(1, 4), hips * 0.5, (slot, 'hip yaw'))
            self.assertGreater(spread(2, 4), chest * 0.5, (slot, 'chest yaw'))
            self.assertGreater(spread(6, 3), arm * 0.5, (slot, 'arm swing'))
            self.assertGreater(spread(4, 4), head * 0.5, (slot, 'head yaw'))
            self.assertGreater(spread(19, 3), plate * 0.2, (slot, 'back plate'))

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
            if slot == 0:                       # the idle's glances are quick: judged over five ticks
                speeds = [sum(speeds[(i + k) % len(speeds)] for k in range(-2, 3)) / 5 for i in range(len(speeds))]
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_parts_penetrate_no_more_than_in_the_chibi_clips(self):
        from tools.models.field_animations import meshclash
        clash = meshclash.Clash(self.new, self.rig)
        worst = {}
        for slot in (0, *TICKS):
            for pose in self.frames(slot)[:-1]:
                world = clash.world(pose)
                for (a, b), most in PENETRATION.items():
                    count, _ = clash.clash(pose, G[a], G[b], world=world)
                    worst[(a, b)] = max(worst.get((a, b), 0), count)
        for pair, most in PENETRATION.items():
            self.assertLessEqual(worst[pair], most, pair)


if __name__ == '__main__':
    unittest.main()
