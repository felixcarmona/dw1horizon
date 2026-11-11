"""Check Kiwimon's walk, tired walk and run (species 282) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 282`; KIWIMON_MODEL names another
path). Before the change it is `kiwimon_gait.PROFILE['source']`: the generator is run on it and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.

Kiwimon faces -z: body 1, rump 2, left leg 3-6 (thigh, shin, ankle pad, toes), right leg 7-10, head 11, lower beak 12.
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
from tools.models.field_animations import kiwimon_gait as gait, quadruped
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = '8c8fa48727e4410c40ae92da5367eee249fa7224ccc08c49b17dbdbb62138ef0'
BONES = 13
TICKS = {2: 14, 3: 18, 4: 10}
IDLE_TICKS = 60
SPEED = {2: 17, 3: 12, 4: 38}
FEET = {'LH': 5, 'RH': 9}                    # the ankle pads: the lowest part of a standing foot
LEFT, RIGHT, BODY = [3, 4, 5, 6], [7, 8, 9, 10], [1, 2]
# leg vertices and triangle centres inside the body or rump meshes in the imported clips (worst sampled tick per slot)
OLD_INSIDE = {0: 146, 2: 117, 3: 135, 4: 197}


class KiwimonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('KIWIMON_MODEL', 'build/imported-model-edit/edit/282-Kiwimon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 282')
        cls.rig = json.loads(Path('content/species/282-kiwimon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[282] = cls.rig
        mmd.exe().bone_count[282] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.PROFILE['source']:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 282
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 282
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._feet = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot):
        """Per tick (closing frame included): each ankle pad's sole pivot with the root's travel and its lowest vertex's height."""
        if slot in self._feet:
            return self._feet[slot]
        np, mesh = self.np, self.mesh
        rig = quadruped.Rig(self.new, self.rig, gait.PROFILE)
        rows = []
        for pose in self.frames(slot):
            W = rig.world(pose)
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
            row = {}
            for name, bone in FEET.items():
                pts = world[mesh.tri[mesh.bone == bone]].reshape(-1, 3)
                height = -float(pts[:, 1].max()) - pose[0][7]
                sole = quadruped.add([W[bone][i][3] for i in range(3)], quadruped.mv(rig.R(W, bone), rig.sole(False)))
                row[name] = (sole[0], -sole[1] - pose[0][7], sole[2] + pose[0][8], height)
            rows.append(row)
        self._feet[slot] = rows
        return rows

    def turns(self, slot):
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

    def worst_inside(self, slot, model=None):
        frames = self.frames(slot, model)
        worst = 0
        for t in range(0, len(frames) - 1):
            worst = max(worst, self.inside_count(frames[t], LEFT + RIGHT, BODY, model))
        return worst

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_idle_the_three_gaits_and_their_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        changed = changed_programs(self.old, self.new)
        self.assertEqual(changed, self.report['changed_slots'])
        self.assertEqual(changed, [0, 2, 3, 4, 33, 36])        # 0 and 33 are the idle and the battle idle it plays; no other slot
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_speeds_and_their_order(self):
        for slot, ticks in TICKS.items():
            self.assertEqual(len(self.frames(slot)) - 1, ticks, slot)
        self.assertEqual(len(set(TICKS.values()) | {IDLE_TICKS}), 4)
        speeds = {}
        for slot in SPEED:
            frames = self.frames(slot)
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertEqual(len(set(steps)), 1, slot)          # the same step every tick
            speeds[slot] = -steps[0]
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

    def test_loops_are_seamless(self):
        for slot in [0] + list(TICKS):
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_clips_differ_and_the_tired_walk_rides_lower(self):
        mean = lambda slot: sum(f[1][7] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3), mean(2))                    # y grows downward
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])
        pitch = lambda slot: sum(f[1][3] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(abs(pitch(4)), abs(pitch(2)))        # the run leans further

    def test_the_legs_are_a_mirrored_pair_half_a_cycle_apart(self):
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            for t in range(ticks):
                u = frames[t]
                v = frames[(t + ticks // 2) % ticks]
                for l, r in zip(LEFT, RIGHT):
                    # the left leg at tick t is the right leg half a cycle later: the same pitch (the shin and thigh
                    # of the walk are solved from mirrored targets), within 4 degrees
                    diff = abs(u[l][3] - v[r][3]) % 4096
                    self.assertLessEqual(min(diff, 4096 - diff), 46, (slot, t, l))

    def test_the_feet_are_planted_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            speed = SPEED[slot]
            for name in FEET:
                stance = [i for i, r in enumerate(rows) if r[name][3] < 3.0]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / speed
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_idle_is_calm_and_alive(self):
        self.assertEqual(len(self.frames(0)) - 1, IDLE_TICKS)
        rows = self.feet(0)
        for name in FEET:                                       # both feet stay planted
            xs, zs = [r[name][0] for r in rows], [r[name][2] for r in rows]
            self.assertLess(max(xs) - min(xs), 4, name)
            self.assertLess(max(zs) - min(zs), 4, name)
            self.assertGreater(min(r[name][3] for r in rows), -4, name)
        for row in self.turns(0):                               # nothing turns quickly
            for b, angle in row.items():
                self.assertLess(angle, 6, b)
        spread = lambda bone, i: max(f[bone][i] for f in self.frames(0)) - min(f[bone][i] for f in self.frames(0))
        self.assertGreater(spread(1, 7), 2)                     # the body breathes
        self.assertGreater(spread(1, 6), 4)                     # and shifts its weight
        self.assertGreater(spread(11, 3), 40)                   # the head nods and pecks (3.5 degrees and more)
        self.assertGreater(spread(2, 3), 20)                    # the chest breathes (the rump rocks)
        yaw = [f[11][4] for f in self.frames(0)]
        self.assertGreater(max(yaw) - min(yaw), 100)            # the head looks about (more than 9 degrees)

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in FEET:
                heights = [r[name][3] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_no_tick_jumps(self):
        for slot in [0] + list(TICKS):
            rows = self.turns(slot)
            for b in range(1, BONES):
                steps = [row[b] for row in rows] * 2
                self.assertLess(max(steps), 50.0, (slot, b))
                for t in range(len(steps) - 1):
                    self.assertLessEqual(abs(steps[t + 1] - steps[t]), 25.0, (slot, b, t % len(rows)))

    def test_no_mesh_tick_jump(self):
        """No tick's average vertex speed passes 2.5 times the clip's median on average (the loop closes)."""
        np, mesh = self.np, self.mesh
        for slot in [0] + list(TICKS):
            speeds = []
            frames = self.frames(slot)
            prev = None
            for pose in frames:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_the_legs_penetrate_the_body_no_more_than_before(self):
        for slot in OLD_INSIDE:
            self.assertLessEqual(self.worst_inside(slot), OLD_INSIDE[slot], slot)


if __name__ == '__main__':
    unittest.main()
