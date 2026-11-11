"""Check Cyclonemon's idle, walk, tired walk and run (species 281) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 281`; CYCLONEMON_MODEL names another
path). Before the change it is `cyclonemon_gait.PROFILE['source']`: the generator is run on it and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.

Cyclonemon faces -z. Its heavy left arm (bones 2-5: shoulder pad, arm column, two claws) is planted like a crutch, the
right arm (6-8) is light, the legs (14-16 right, 17-19 left) hang from the hips (13). Bone 1 is scaled by 1.3.
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
from tools.models.field_animations import cyclonemon_gait as gait, quadruped
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = '3878263746006a99434fc9e48ece494508ff8295c8b8f624cb888a52f3573fdc'
BONES = 23
TICKS = {0: 48, 2: 18, 3: 26, 4: 12}
SPEED = {2: 15, 3: 11, 4: 38}
FEET = {'claw': 4, 'RH': 16, 'LH': 19}
PAD, TORSO, HEAD = [2, 3], [1], [9, 10, 11, 12]


class CyclonemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('CYCLONEMON_MODEL', 'build/imported-model-edit/edit/281-Cyclonemon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 281')
        cls.rig = json.loads(Path('content/species/281-cyclonemon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[281] = cls.rig
        mmd.exe().bone_count[281] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.PROFILE['source']:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 281
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 281
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._feet = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot):
        """Per tick (the closing frame too): each foot's sole pivot, in the world with the root's travel, and the height of
        the lowest vertex of its bone over the floor."""
        if slot in self._feet:
            return self._feet[slot]
        np, mesh = self.np, self.mesh
        rig = quadruped.Rig(self.new, self.rig, gait.PROFILE)
        rows = []
        for pose in self.frames(slot):
            W = rig.world(pose)
            p = copy.deepcopy(pose)
            p[0] = [4096]*3 + [0]*6
            world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
            row = {}
            for name, bone in FEET.items():
                pts = world[mesh.tri[mesh.bone == bone]].reshape(-1, 3)
                height = -float(pts[:, 1].max()) - pose[0][7]
                sole = quadruped.add([W[bone][i][3] for i in range(3)], quadruped.mv(rig.R(W, bone), rig.sole(name == 'claw')))
                row[name] = (sole[0], -sole[1] - pose[0][7], sole[2] + pose[0][8], height)
            rows.append(row)
        self._feet[slot] = rows
        return rows

    def turns(self, slot):
        """Per tick and bone: the angle (degrees) the bone's world rotation turns to the next tick."""
        import math
        rig = quadruped.Rig(self.new, self.rig, gait.PROFILE)
        worlds = []
        for pose in self.frames(slot):
            W = rig.world(pose)
            worlds.append({b: rig.R(W, b) for b in range(1, BONES)})
        out = []
        for t in range(len(worlds) - 1):
            row = {}
            for b in range(1, BONES):
                A, B = worlds[t][b], worlds[t + 1][b]
                cos = (sum(A[i][j] * B[i][j] for i in range(3) for j in range(3)) - 1) / 2
                row[b] = math.degrees(math.acos(max(-1.0, min(1.0, cos))))
            out.append(row)
        return out

    def inside_count(self, pose, a_bones, b_bones):
        """Vertices and triangle centres of a_bones inside the closed meshes of b_bones (majority of five rays)."""
        np, mesh = self.np, self.mesh
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_the_battle_alias_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        changed = changed_programs(self.old, self.new)
        self.assertEqual(changed, self.report['changed_slots'])
        self.assertEqual(changed, [0, 2, 3, 4, 33])         # 0 and 33 are the idle and the battle idle it plays
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        for slot, ticks in TICKS.items():
            self.assertEqual(len(self.frames(slot)) - 1, ticks, slot)
        self.assertEqual(len({t for t in TICKS.values()}), 4)           # four different lengths
        speeds = {}
        for slot in SPEED:
            frames = self.frames(slot)
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertEqual(len(set(steps)), 1, slot)                   # the same step every tick
            speeds[slot] = -steps[0]
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
                    self.assertEqual((first[b][i] - last[b][i]) % 4096 in (0, 1, 4095), True, (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_clips_differ(self):
        def spread(slot, bone, i):
            values = [f[bone][i] for f in self.frames(slot)]
            return max(values) - min(values)
        for slot in (2, 3, 4):
            self.assertGreater(spread(slot, 1, 7), 3)                    # the body bobs
        self.assertGreater(spread(4, 1, 7), spread(2, 1, 7))             # more in the run
        low = lambda slot: sum(f[1][7] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(low(3), low(2))                               # the tired walk rides lower (y grows downward)
        for a, b in ((0, 2), (2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_idle_is_calm(self):
        rows = self.feet(0)
        for name in FEET:                                               # the feet stay planted
            xs = [r[name][0] for r in rows]
            zs = [r[name][2] for r in rows]
            self.assertLess(max(xs) - min(xs), 6, name)
            self.assertLess(max(zs) - min(zs), 6, name)
        for row in self.turns(0):                                       # and nothing turns quickly
            for b, angle in row.items():
                self.assertLess(angle, 6, b)

    def test_the_feet_are_planted_in_stance(self):
        for slot in (2, 3, 4):
            rows = self.feet(slot)                                       # the closing frame included: no wrap-around
            speed = SPEED[slot]
            for name in FEET:
                stance = [i for i, r in enumerate(rows) if r[name][1] < 6.5]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / speed
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_feet_stay_above_the_floor(self):
        for slot in TICKS:
            for r in self.feet(slot):
                for name, (x, pivot, z, h) in r.items():
                    self.assertGreater(h, -4, (slot, name))

    def test_no_tick_jumps(self):
        """No bone turns more than 40 degrees in a tick (the run's arm turns fastest), and no turn is more than 20 degrees
        faster than the tick before or after it: a planted limb crawls through its stance and swings through the rest of
        the cycle in a smooth bell, never in a snap."""
        for slot in (2, 3, 4):
            rows = self.turns(slot)
            for b in range(1, BONES):
                steps = [row[b] for row in rows] * 2            # the loop closes: the last tick leads into the first
                self.assertLess(max(steps), 40.0, (slot, b))
                for t in range(len(steps) - 1):
                    self.assertLessEqual(abs(steps[t + 1] - steps[t]), 20.0, (slot, b, t % len(rows)))

    def test_the_shoulder_pad_stays_by_the_torso_and_head(self):
        """The pad and the arm column barely sink into the torso or the head (the original poses overlap by up to 30 and 35)."""
        for slot in TICKS:
            frames = self.frames(slot)
            for t in range(0, len(frames) - 1, max(1, (len(frames) - 1) // 6)):
                self.assertLessEqual(self.inside_count(frames[t], PAD, TORSO), 45, (slot, t))
                self.assertLessEqual(self.inside_count(frames[t], PAD, HEAD), 35, (slot, t))

    def test_the_legs_stay_out_of_the_body(self):
        legs = [14, 15, 16, 17, 18, 19]
        for slot in TICKS:
            frames = self.frames(slot)
            for t in range(0, len(frames) - 1, max(1, (len(frames) - 1) // 6)):
                self.assertLessEqual(self.inside_count(frames[t], legs, TORSO), 12, (slot, t))
                self.assertLessEqual(self.inside_count(frames[t], [6, 7, 8], [14, 15, 16]), 12, (slot, t))


if __name__ == '__main__':
    unittest.main()
