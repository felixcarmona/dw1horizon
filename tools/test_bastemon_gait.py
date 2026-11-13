"""Check Bastemon's idle, walk, tired walk and run (species 432) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 432`; BASTEMON_MODEL names another path):
the imported model, to which the overlay applies the chibi proportions, the celebrations and then these clips. The test runs
`bastemon_gait.build` on it (a few seconds) and checks the result.

Bastemon faces -z: body 1, hips 11, right leg 12-15 (thigh, shin, ankle, foot), left leg 16-19, head 8 with hair 9-10, left arm
2-4 (shoulder cap, upper arm, forearm), right arm 5-7, ribbons 20-22 (left) and 23-25 (right).
"""
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import bastemon_gait as gait

BONES = 26
PARTS = dict(armL=[2, 3, 4], armR=[5, 6, 7], head=[8], hair=[9, 10], legR=[12, 13, 14, 15], legL=[16, 17, 18, 19], hips=[11], torso=[1],
             ribL=[20, 21, 22], ribR=[23, 24, 25])
# the most vertices and triangle centres of the first part inside the second, in any tick of any clip (the idle and the three gaits).
# The chibi build's own clips measure the same pairs at 346 vertices in total (the pair maxima summed), these at 344: ten pairs grow by
# 1 to 8 vertices (ribbon against arm and thigh, forearm and head against the torso, the thighs against the hips in the tired walk), the
# rest shrink. Pinned so they cannot grow.
PENETRATION = {
    ('armL', 'ribL'): 5,
    ('armL', 'torso'): 22,
    ('armR', 'torso'): 22,
    ('hair', 'head'): 22,
    ('head', 'hair'): 9,
    ('head', 'torso'): 13,
    ('hips', 'legL'): 2,
    ('hips', 'legR'): 2,
    ('hips', 'torso'): 24,
    ('legL', 'hips'): 16,
    ('legL', 'legR'): 24,
    ('legR', 'hips'): 14,
    ('legR', 'legL'): 24,
    ('legR', 'ribR'): 6,
    ('ribL', 'armL'): 8,
    ('ribL', 'hips'): 16,
    ('ribL', 'legL'): 2,
    ('ribL', 'ribR'): 6,
    ('ribR', 'hips'): 16,
    ('ribR', 'legR'): 2,
    ('ribR', 'ribL'): 7,
    ('torso', 'armL'): 14,
    ('torso', 'armR'): 15,
    ('torso', 'head'): 30,
    ('torso', 'hips'): 23,
}
TICKS = {2: 24, 3: 28, 4: 20}               # each clip is two different cycles of 12, 14 and 10 ticks
IDLE_TICKS = 60
SPEED = {2: 15, 3: 10.5, 4: 36}
FEET = {'LH': 19, 'RH': 15}
G = dict(arms=[2, 3, 4, 5, 6, 7], head=[8], hair=[9, 10], ribbons=[20, 21, 22, 23, 24, 25])


class BastemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('BASTEMON_MODEL', 'build/imported-model-edit/edit/432-Bastemon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 432')
        cls.rig = json.loads(Path('content/species/432-bastemon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[432] = cls.rig
        mmd.exe().bone_count[432] = BONES
        cls.data, cls.proof = gait.build(path.read_bytes(), cls.rig)
        cls.report = cls.proof['gait']
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 432
        cls.clips = {s: animsheet.slot_frames(cls.new, BONES, s)[0] for s in (0, 2, 3, 4)}

    def test_storage_fits_the_resident_buffer(self):
        self.assertLess(self.report['storage']['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        self.assertEqual(len(self.clips[0]) - 1, IDLE_TICKS)
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.clips[slot]
            self.assertEqual(len(frames) - 1, ticks)
            speeds[slot] = abs(frames[-1][0][8] - frames[0][0][8]) / ticks
            self.assertAlmostEqual(speeds[slot], SPEED[slot], delta=0.5)
        self.assertTrue(10 <= speeds[3] < speeds[2] < speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 35 <= speeds[4] <= 52 and speeds[3] <= 20)

    def test_loops_are_seamless(self):
        for slot, frames in self.clips.items():
            for a, b in zip(frames[0][1:], frames[-1][1:]):
                self.assertTrue(all(abs((x - y + 2048) % 4096 - 2048) <= 2 for x, y in zip(a[3:6], b[3:6])), slot)

    def test_the_idle_stands_still(self):
        self.assertEqual(self.clips[0][0][0][8], self.clips[0][-1][0][8])
        self.assertEqual(self.report['checks'][0]['stance_slip'], {'RH': 0.0, 'LH': 0.0})

    def test_the_feet_are_planted_in_stance(self):
        for row in self.report['checks'][1:]:
            self.assertLess(max(row['stance_slip'].values()), 0.12, row['gait'])

    def test_no_sole_is_below_the_floor(self):
        for row in self.report['checks']:
            self.assertLess(row['lowest_point'], 1.0, row['gait'])     # positive = under the floor, in units

    def test_the_studio_measures_a_planted_walk(self):
        import animstudio
        for slot, mean, worst in ((2, 25, 45), (3, 25, 45), (4, 25, 45)):
            model = animstudio.Model(f'{self._path()}:432:{self._tim()}', slot)
            _, rows = animstudio.metrics(model)
            for row in rows:
                self.assertLess(row[3], mean, slot)
                self.assertLess(row[4], worst, slot)

    def _tim(self):
        model = Path(os.environ.get('BASTEMON_MODEL', 'build/imported-model-edit/edit/432-Bastemon.MMD'))
        return model.with_suffix('.TIM')

    def _path(self):
        p = Path(os.environ.get('TMPDIR', '/tmp')) / 'bastemon-gait-test.MMD'
        p.write_bytes(self.data)
        return p

    def test_the_whole_body_moves_with_the_stride(self):
        def swing(frames, bone, channel):
            values = [f[bone][channel] for f in frames]
            return (max(values) - min(values)) * 360 / 4096
        for slot in (2, 3, 4):
            frames = self.clips[slot]
            for name, minimum in (('arms', 12), ('head', 3), ('hair', 4), ('ribbons', 4)):
                best = max(max(swing(frames, b, c) for c in (3, 4, 5)) for b in G[name])
                self.assertGreater(best, minimum, (slot, name))

    def test_the_arms_swing_against_the_legs_on_their_sides(self):
        import animstudio
        import numpy as np
        for slot in (2, 4):
            model = animstudio.Model(f'{self._path()}:432:{self._tim()}', slot)
            zs = {b: [] for b in (4, 7, 15, 19)}
            for t in range(len(model.frames) - 1):
                pose, _ = model.pose(t)
                mats = mmd.bone_matrices(model.m, pose)
                for b in zs:
                    zs[b].append(mats[b][2][3])
            z = {b: np.array(v) - np.mean(v) for b, v in zs.items()}
            corr = lambda a, b: float(np.corrcoef(z[a], z[b])[0, 1])
            self.assertGreater(corr(4, 15), 0.5)      # left hand with the right foot
            self.assertLess(corr(4, 19), -0.5)
            self.assertGreater(corr(7, 19), 0.5)

    def test_parts_penetrate_no_more_than_pinned(self):
        import copy
        import numpy as np
        import animstudio
        from types import SimpleNamespace
        from tools.test_tortomon_gait import inside, DIRS
        mesh = animstudio.FastMesh(SimpleNamespace(m=self.new, skel=self.rig))
        worst = {}
        for slot in (0, 2, 3, 4):
            for frame in self.clips[slot][:-1:3]:
                pose = copy.deepcopy(frame)
                pose[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, pose)).astype(float)
                tris = {a: world[mesh.tri[np.isin(mesh.bone, bones)]] for a, bones in PARTS.items()}
                for a in PARTS:
                    points = np.vstack([tris[a].reshape(-1, 3), tris[a].mean(1)])
                    for b in PARTS:
                        if a != b:
                            votes = sum(inside(np, points, tris[b], d).astype(int) for d in DIRS)
                            worst[(a, b)] = max(worst.get((a, b), 0), int((votes >= 3).sum()))
        for pair, count in worst.items():
            self.assertLessEqual(count, PENETRATION.get(pair, 0), pair)

    def test_no_bone_jumps_between_ticks(self):
        import copy
        import numpy as np
        # world position of every bone with the root's travel taken out: a tick's step against the bone's median step
        legs = {13, 14, 15, 17, 18, 19}       # a swinging foot is several times faster than a planted one, in any gait
        for slot in (0, 2, 3, 4):
            points = []
            for frame in self.clips[slot]:
                pose = copy.deepcopy(frame)
                pose[0] = [4096] * 3 + [0] * 6
                mats = mmd.bone_matrices(self.new, pose)
                points.append(np.array([[mats[b][i][3] for i in range(3)] for b in range(1, BONES)], float))
            steps = np.linalg.norm(np.diff(np.array(points), axis=0), axis=2)
            median = np.median(steps, axis=0)
            for i in range(BONES - 1):
                if median[i] > 2:
                    self.assertLess(steps[:, i].max() / median[i], 4.0 if i + 1 in legs else 2.5, (slot, i + 1))

    def test_no_tick_jumps(self):
        for slot, frames in self.clips.items():
            for bone in range(1, BONES):
                for channel in (3, 4, 5):
                    steps = [abs((frames[t + 1][bone][channel] - frames[t][bone][channel] + 2048) % 4096 - 2048) for t in range(len(frames) - 1)]
                    self.assertLess(max(steps), 4096 * 0.3, (slot, bone, channel))


if __name__ == '__main__':
    unittest.main()
