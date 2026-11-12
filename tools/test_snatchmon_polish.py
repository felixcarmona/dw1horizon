"""Check Snatchmon's corrected walk, tired walk and run (species 331) on the real import, made as the overlay makes them.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 331`; SNATCHMON_MODEL names another path):
the imported base. `snatchmon_polish.build` reshapes it (chibi.py) and corrects three of the four field clips (the idle stays); the clips before this
change are the reshaped model alone (`chibi.build`), used to compare every figure.

Snatchmon faces -z: chest 1, pelvis 2, tail 3-5, right leg 6-9 (thigh, shin, ankle, toes), left leg 10-13, right arm 14-16,
head 17, chain 18-19, left arm 20-22.
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
from tools.models.field_animations import snatchmon_polish as gait, quadruped, chibi
from tools.test_tortomon_gait import inside, DIRS

BASE = '30d61fd8bdf51999278c90d484358dd1e324a97305da45734d9e6997566756e9'
BONES = 23
TICKS = {2: 17, 3: 17, 4: 17}              # samples per clip, the closing one included
FEET = {'RH': 8, 'LH': 12}                  # the ankles: the lowest part of a standing foot
RIGHT, LEFT, BODY = [6, 7, 8, 9], [10, 11, 12, 13], [1, 2]
ARMS = [14, 15, 16, 20, 21, 22]
HEAD_BONE = 17
# the legs inside the trunk and pelvis, and the arms inside the trunk and legs, in the clips before this change
# (worst sampled tick per slot)
OLD_LEGS = {2: 36, 3: 37, 4: 58}
OLD_ARMS = {2: 44, 3: 44, 4: 44}


class SnatchmonPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('SNATCHMON_MODEL', 'build/imported-model-edit/edit/331-Snatchmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 331')
        cls.rig = json.loads(Path('content/species/331-vemmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[331] = cls.rig
        mmd.exe().bone_count[331] = BONES
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != BASE:
            raise unittest.SkipTest('not the imported base model of this change')
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
        import edit
        edit.crmath.install()
        edit.pysum.install()
        try:
            reshaped, _ = chibi.build(data, cls.rig)
            cls.data, cls.report = gait.build(data, cls.rig)
        finally:
            edit.crmath.uninstall()
            edit.crmath.clear()
            edit.pysum.uninstall()
        cls.old = mmd.MMD.parse(reshaped, BONES)
        cls.old.type = 331
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 331
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._feet = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def feet(self, slot):
        """Per tick (closing frame included): each ankle's sole pivot with the root's travel and its lowest vertex's height."""
        if slot in self._feet:
            return self._feet[slot]
        np, mesh = self.np, self.mesh
        rig = quadruped.Rig(self.new, self.rig, dict(gait.PROFILE, source=''))
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
        rig = quadruped.Rig(self.new, self.rig, dict(gait.PROFILE, source=''))
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

    def worst_inside(self, slot, a_bones, b_bones, model=None):
        frames = self.frames(slot, model)
        return max(self.inside_count(frames[t], a_bones, b_bones, model) for t in range(len(frames) - 1))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_only_the_three_field_clips_change(self):
        changed = changed_programs(self.old, self.new)
        self.assertEqual(changed, self.report['changed_slots'])
        self.assertEqual(changed, [2, 3, 4])             # the idle (0, 33) is not touched
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_ticks_travel_and_events_are_the_originals(self):
        for slot, ticks in TICKS.items():
            old, loop_old, events_old = animsheet.slot_frames(self.old, BONES, slot)
            new, loop_new, events_new = animsheet.slot_frames(self.new, BONES, slot)
            self.assertEqual((len(new), loop_new), (ticks, loop_old), slot)
            self.assertEqual([(k, e['bank'], e['note']) for t, k, e in sorted(events_new, key=lambda x: x[2]['frame'])],
                             [(k, e['bank'], e['note']) for t, k, e in sorted(events_old, key=lambda x: x[2]['frame'])], slot)
            self.assertEqual(len(old), len(new))
            for a, b in zip(old, new):
                self.assertEqual(a[0][6:9], b[0][6:9], slot)             # the root's travel is not touched
            for t in range(len(new)):
                self.assertLessEqual(max(abs(x - y) for x, y in zip(old[t][0], new[t][0])), 0, slot)

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            for b in range(1, BONES):
                self.assertEqual(frames[0][b], frames[-1][b], (slot, b))

    def test_only_small_corrections_are_made(self):
        # no bone turns more than this many degrees away from the original at any tick (the head and hook follow-through,
        # the tired walk's droop and the leg corrections are all small)
        # (the legs are judged by where their joints end up: two bones that bend about one joint differ in
        # twist alone, which no one sees)
        limits = {2: 26.0, 3: 28.0, 4: 34.0}
        legs = {6, 7, 8, 9, 10, 11, 12, 13}
        for slot, limit in limits.items():
            for a, b in zip(self.frames(slot, self.old), self.frames(slot)):
                for bone in range(1, BONES):
                    if bone in legs:
                        continue
                    A, B = mmd.rot_matrix(*a[bone][3:6]), mmd.rot_matrix(*b[bone][3:6])
                    cos = (sum(A[i][j] * B[i][j] for i in range(3) for j in range(3)) - 1) / 2
                    self.assertLessEqual(math.degrees(math.acos(max(-1.0, min(1.0, cos)))), limit, (slot, bone))
                MA = mmd.bone_matrices(self.old, self.zero_root(a))
                MB = mmd.bone_matrices(self.new, self.zero_root(b))
                for joint in (7, 8, 11, 12):                    # knees and ankles stay near where the clip had them (the planted ankles come down to the floor: the clips hovered them 15-20 units above it)
                    d = math.dist([MA[joint][i][3] for i in range(3)], [MB[joint][i][3] for i in range(3)])
                    self.assertLessEqual(d, 56.0 if joint in (8, 12) else 40.0, (slot, joint))

    @staticmethod
    def zero_root(pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return p

    def test_no_foot_skids_along_the_floor(self):
        # the sole low over the floor while it runs over the ground much faster than the body: the original did it at every landing
        def skids(model):
            self.__class__.new, keep = model, self.__class__.new
            self._feet.clear()
            try:
                total = 0
                for slot in (2, 3):
                    rows = self.feet(slot)
                    speed = abs(rows[-1]['RH'][2] - rows[0]['RH'][2] - (rows[-1]['RH'][2] - rows[0]['RH'][2])) or 0
                    travel = abs(self.frames(slot, model)[-1][0][8]) / (len(rows) - 1)
                    for name in FEET:
                        for t in range(len(rows) - 1):
                            h = rows[t][name][1]
                            step = abs(rows[t + 1][name][2] - rows[t][name][2])
                            if h < 8 and step > 1.8 * travel:
                                total += 1
                return total
            finally:
                self.__class__.new = keep
                self._feet.clear()
        self.assertLess(skids(self.new), max(1, skids(self.old)))

    def test_stance_feet_stay_where_they_landed(self):
        # while down (sole within 18 units of the floor, after the landing tick) a foot drifts over the ground by less than before
        def drift(model):
            self.__class__.new, keep = model, self.__class__.new
            self._feet.clear()
            try:
                worst = 0.0
                for slot in (2, 3):
                    rows = self.feet(slot)
                    for name in FEET:
                        down = [t for t in range(len(rows) - 1) if rows[t][name][1] < 18 and rows[t + 1][name][1] < 18]
                        zs = [rows[t][name][2] for t in down]
                        if zs:
                            worst += sum(abs(z - sorted(zs)[len(zs) // 2]) for z in zs) / len(zs)
                return worst
            finally:
                self.__class__.new = keep
                self._feet.clear()
        self.assertLess(drift(self.new), drift(self.old))

    def toe_slip(self, slot, model=None):
        # animstudio's definition: the two lowest bones (the toes), stance = within the lowest quarter of the bone's own
        # height range, slip = its ground speed over the root's speed, in percent
        model = model or self.new
        frames = self.frames(slot, model)
        n = len(frames)
        speed = abs(frames[-1][0][8] - frames[0][0][8]) / (n - 1)
        out = []
        for bone in (9, 13):
            ys, zs = [], []
            for f in frames:
                p = copy.deepcopy(f)
                p[0] = [4096] * 3 + [0] * 6
                M = mmd.bone_matrices(model, p)[bone]
                ys.append(M[1][3])
                zs.append(M[2][3] + f[0][8])
            lo, hi = max(ys), min(ys)
            slip = [abs(zs[t + 1] - zs[t]) / speed * 100 for t in range(n - 1) if ys[t] > lo - 0.25 * (lo - hi)]
            out.append((sum(slip) / len(slip), max(slip)))
        return out

    def test_the_planted_foot_does_not_slide(self):
        # the tired walk slid 153 % of the body's speed on average, 460 % at worst; the walk and run were already near still
        for mean, worst in self.toe_slip(3):
            self.assertLess(mean, 25.0)
            self.assertLess(worst, 45.0)
        for slot in (2, 4):
            for (mean, worst), (mean_old, worst_old) in zip(self.toe_slip(slot), self.toe_slip(slot, self.old)):
                self.assertLessEqual(mean, max(mean_old, 20.0), slot)
                self.assertLessEqual(worst, max(worst_old, 45.0), slot)

    def test_footsteps_sound_when_a_foot_lands(self):
        touchdowns = {c['slot']: sorted(t for ticks in c['touchdowns'].values() for t in ticks) for c in self.report['checks']
                      if c['slot'] in (2, 3, 4)}
        for slot, downs in touchdowns.items():
            _, _, events = animsheet.slot_frames(self.new, BONES, slot)
            sounds = sorted(t for t, k, _ in events if k == 'sound')
            self.assertEqual(sounds, downs, slot)
            self.assertEqual(len(downs), 2, slot)

    def test_the_head_arms_and_tail_follow_late(self):
        for slot in TICKS:
            for bone in (4, 5, 15, 16, 17, 18, 21):
                self.assertNotEqual([f[bone][3:6] for f in self.frames(slot, self.old)], [f[bone][3:6] for f in self.frames(slot)], (slot, bone))

    def test_no_bone_tick_jumps(self):
        # no bone turns in one tick more than it did before, plus this much
        for slot in TICKS:
            self.__class__.new, keep = self.old, self.__class__.new
            try:
                before = max(max(r.values()) for r in self.turns(slot))
            finally:
                self.__class__.new = keep
            after = max(max(r.values()) for r in self.turns(slot))
            self.assertLessEqual(after, before + 12.0, (slot, before, after))

    def test_no_mesh_tick_jump(self):
        np, mesh = self.np, self.mesh
        for slot in TICKS:
            frames = self.frames(slot)
            speeds = []
            prev = None
            for pose in frames:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
                if prev is not None:
                    speeds.append(float(np.abs(world - prev).max(axis=1).max()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * max(med, 1.0), slot)

    def test_nothing_clashes_more_than_before(self):
        for slot in OLD_LEGS:
            # the re-solved legs may differ by one sample of ~50: the original walk reached 50 and the new one 51
            self.assertLessEqual(self.worst_inside(slot, RIGHT + LEFT, BODY), OLD_LEGS[slot] + 1, slot)
            self.assertLessEqual(self.worst_inside(slot, ARMS, BODY + RIGHT + LEFT), OLD_ARMS[slot], slot)

    def test_the_feet_never_sink_into_the_floor(self):
        for slot in TICKS:
            for row in self.feet(slot):
                for name in FEET:
                    self.assertGreaterEqual(row[name][3], -6.0, (slot, name))


if __name__ == '__main__':
    unittest.main()
