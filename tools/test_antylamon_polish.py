"""Check Antylamon's walk (species 309, slot 2) on the real import, made as the overlay makes it.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 309`; ANTYLAMON_MODEL names another path).
The overlay's input is that import with its slot aliases applied; `antylamon_polish.build` reshapes it (chibi.py) and
smooths the walk. The clips before this change are the reshaped model alone (`chibi.build`), used to compare every figure.

Antylamon faces -z: pelvis 1 and 2, right leg 3-6 (thigh, shin, ankle, toes), left leg 7-10, chest 11-12, shoulders 13 and 16
(the two arms hang from these: elbows and hands do not turn), head 19-21.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import antylamon_polish as gait, chibi
from tools.models.field_animations.okuwamon_limbs import Body, exp_so3, log_so3

BASE = '15e07d0b929c03ab295a54a4b2dda99d1956db5d5dc1cbe34058c96b2dfc948e'   # the overlay's input
NB = 22
LIMIT = 100352
RIGHT, LEFT = (3, 4, 5, 6), (7, 8, 9, 10)
ARM_L, ARM_R = (13, 14, 15), (16, 17, 18)
BODY = (1, 2, 11, 12, 19, 20, 21)
GROUPS = {'legR': RIGHT, 'legL': LEFT, 'armL': ARM_L, 'armR': ARM_R}
# the ticks each toe's hinge is over the floor (the stance), steps from tick to tick, in the clip before this change
WINDOW = {6: range(5, 10), 10: range(13, 18)}
# the legs inside the body or each other and the arms inside the body or legs, in the clip before this change
OLD_PENETRATION = 0


def angle_between(a, b):
    return math.degrees(float(__import__('numpy').linalg.norm(log_so3(a.T @ b))))


class AntylamonPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('ANTYLAMON_MODEL', 'build/imported-model-edit/edit/309-Antylamon.MMD'))
        tim = path.with_suffix('.TIM')
        if not path.exists() or not tim.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 309')
        record = json.loads(Path('content/species/309-antylamon.json').read_text())
        cls.rig = record['model']['skeleton']
        mmd.exe().skeleton[309] = cls.rig
        mmd.exe().bone_count[309] = NB
        sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
        import edit
        import species as species_tools
        record['model']['file'] = str(path)
        record['texture'] = {'file': str(tim)}
        record['_path'] = str(Path('content/species/309-antylamon.json').resolve())
        edit.crmath.install()
        edit.pysum.install()
        try:
            data = species_tools.species_model(record)[0]
            if hashlib.sha256(data).hexdigest() != BASE:
                raise unittest.SkipTest('not the import this change was made on')
            reshaped, _ = chibi.build(data, cls.rig)
            cls.data, cls.proof = gait.build(data, cls.rig)
        finally:
            edit.crmath.uninstall()
            edit.crmath.clear()
            edit.pysum.uninstall()
        cls.old = mmd.MMD.parse(reshaped, NB)
        cls.old.type = 309
        cls.new = mmd.MMD.parse(cls.data, NB)
        cls.new.type = 309
        import animstudio
        cls.meshes = {id(m): animstudio.FastMesh(type('M', (), dict(m=m, skel=cls.rig))()) for m in (cls.old, cls.new)}
        cls._cache = {}

    # ------------------------------------------------------------------ helpers
    def frames(self, model, slot=2):
        return animsheet.slot_frames(model, NB, slot)[0]

    def world(self, model, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return self.meshes[id(model)].world(mmd.bone_matrices(model, p)).astype(float)

    def worlds(self, model):
        key = ('worlds', id(model))
        if key not in self._cache:
            self._cache[key] = [self.world(model, f) for f in self.frames(model)[:-1]]
        return self._cache[key]

    def indices(self, model, bones):
        return self.np.concatenate([self.np.arange(a, a + k) for b, a, k in self.meshes[id(model)].slices if b in bones])

    def steps(self, model, bones=None):
        """Per tick (round the loop) the mean distance the vertices of `bones` (all when None) move to the next tick, root motion
        removed, and the largest over the median."""
        np = self.np
        w = self.worlds(model)
        idx = None if bones is None else self.indices(model, bones)
        d = []
        for t in range(len(w)):
            a, b = w[(t + 1) % len(w)], w[t]
            d.append(float(np.linalg.norm((a - b) if idx is None else (a[idx] - b[idx]), axis=1).mean()))
        return d, max(d) / float(np.median(d))

    def accelerations(self, model, bone):
        """Degrees per tick per tick: how much the bone's local turn from one tick to the next changes (round the loop)."""
        np = self.np
        n = len(self.frames(model)) - 1
        rots = [np.array(mmd.rot_matrix(*f[bone][3:6]), float)[:3, :3] for f in self.frames(model)[:n]]
        omega = [log_so3(rots[t].T @ rots[(t + 1) % n]) * 180 / math.pi for t in range(n)]
        return [float(np.linalg.norm(omega[t] - omega[t - 1])) for t in range(n)]

    def deviation(self, model, bone):
        """Degrees each tick's local rotation lies from the middle of its two neighbours' (cyclic)."""
        np = self.np
        n = len(self.frames(model)) - 1
        rots = [np.array(mmd.rot_matrix(*f[bone][3:6]), float)[:3, :3] for f in self.frames(model)[:n]]
        out = []
        for t in range(n):
            a, c = rots[t - 1], rots[(t + 1) % n]
            mid = a @ exp_so3(0.5 * log_so3(a.T @ c))
            out.append(angle_between(mid, rots[t]))
        return out

    def toe_slip(self, model, bone):
        """Percent of the root's speed the toe hinge moves over the floor, tick to tick, over the stance steps (mean, worst)."""
        frames = self.frames(model)
        speed = abs(frames[-1][0][8] - frames[0][0][8]) / (len(frames) - 1)
        z = []
        for f in frames:
            p = copy.deepcopy(f)
            p[0] = [4096] * 3 + [0] * 6
            z.append(mmd.bone_matrices(model, p)[bone][2][3] + f[0][8])
        v = [abs(z[t % 16 + 1] - z[t % 16]) / speed * 100 for t in WINDOW[bone]]
        return sum(v) / len(v), max(v)

    # ------------------------------------------------------------------ what must not change
    def test_only_the_walk_changed(self):
        table = self.old.anims.table
        self.assertEqual(self.new.anims.table, table)
        self.assertEqual(changed_programs(self.old, self.new), [2])
        self.assertEqual(table.count(table[2]), 1, 'no other slot shares the walk program')
        self.assertEqual(self.new.tmd.build(), self.old.tmd.build(), 'the mesh')
        for slot, index in enumerate(table):
            if index is None or slot == 2:
                continue
            self.assertEqual(self.new.anims.anims[index].build(), self.old.anims.anims[index].build(), 'slot %d' % slot)
        # the idle, the tired walk and the run, played back, are the same poses and the same root motion
        for slot in (0, 3, 4, 33):
            self.assertEqual(self.frames(self.new, slot), self.frames(self.old, slot), 'slot %d' % slot)

    def test_walk_keeps_its_ticks_root_motion_and_sounds(self):
        old, new = self.frames(self.old), self.frames(self.new)
        self.assertEqual(len(new), 17)
        self.assertEqual([f[0] for f in new], [f[0] for f in old], 'root motion, tick by tick')
        self.assertEqual(animsheet.slot_frames(self.new, NB, 2)[2], animsheet.slot_frames(self.old, NB, 2)[2], 'the sounds')
        self.assertEqual(animsheet.slot_frames(self.new, NB, 2)[1], animsheet.slot_frames(self.old, NB, 2)[1])

    def test_loop_closes(self):
        new = self.frames(self.new)
        for b in range(1, NB):
            self.assertEqual(new[0][b], new[-1][b], 'bone %d' % b)

    def test_only_the_shoulders_and_the_leg_chains_turn_differently(self):
        old, new = self.frames(self.old), self.frames(self.new)
        changed = {b for b in range(1, NB) if any(o[b] != n[b] for o, n in zip(old, new))}
        self.assertLessEqual(changed, {13, 16, 3, 4, 5, 7, 8, 9}, changed)

    def test_buffer(self):
        resident = motionstorage.audit(self.data, NB)['resident_bytes']
        self.assertLess(resident, LIMIT)
        self.assertLess(resident, motionstorage.audit(self.old.build(), NB)['resident_bytes'] + 600)

    # ------------------------------------------------------------------ the arms
    def test_the_stray_shoulder_key_was_there_and_is_gone(self):
        # before: one key of each shoulder about 24 degrees off the middle of its neighbours, half a loop apart
        for bone, tick in ((13, 14), (16, 6)):
            before = self.deviation(self.old, bone)
            self.assertGreater(before[tick], 20)
            self.assertEqual(max(range(len(before)), key=lambda t: before[t]), tick)
            self.assertLess(max(self.deviation(self.new, bone)), 8, bone)
        self.assertEqual(self.proof['stray_keys'], {13: [13, 14, 15], 16: [5, 6, 7]})

    def test_arms_have_no_tick_jump(self):
        for name, bones in (('left arm', ARM_L), ('right arm', ARM_R)):
            before = self.steps(self.old, bones)
            after = self.steps(self.new, bones)
            self.assertGreater(before[1], 5, name)           # the snap: the hand moved six times the median
            self.assertLess(after[1], 2.0, name)             # smooth: no tick moves the arm 2 x the median
            self.assertLess(max(after[0]), max(before[0]) / 2.5, name)

    def test_shoulders_turn_steadily(self):
        for bone in (13, 16):
            self.assertLess(max(self.accelerations(self.new, bone)), 12, bone)       # before 48 degrees per tick per tick
            self.assertGreater(max(self.accelerations(self.old, bone)), 40, bone)

    def test_arms_keep_their_swing(self):
        np = self.np
        for bone in (13, 16):
            for ch in range(3, 6):
                old = [f[bone][ch] for f in self.frames(self.old)]
                new = [f[bone][ch] for f in self.frames(self.new)]
                # outside the repaired keys nothing moved, and the swing's size is the same
                self.assertLess(abs(np.ptp(new) - np.ptp(old)), 130, (bone, ch))

    # ------------------------------------------------------------------ the legs
    def test_legs_lift_off_without_a_kink(self):
        for bones in (RIGHT, LEFT):
            for bone in bones[:2]:
                self.assertLess(max(self.accelerations(self.new, bone)), 35, bone)        # before 70 (shin), 38 (thigh)
                self.assertLess(max(self.accelerations(self.new, bone)), max(self.accelerations(self.old, bone)))
            for bone in bones[2:]:
                self.assertLessEqual(max(self.accelerations(self.new, bone)), max(self.accelerations(self.old, bone)) + 0.5)
        before, after = self.steps(self.old, RIGHT + LEFT), self.steps(self.new, RIGHT + LEFT)
        self.assertLess(after[1], 1.6)
        self.assertLess(after[1], before[1])
        self.assertLess(max(after[0]), max(before[0]) * 0.9)

    def test_the_foot_no_longer_hops_for_one_tick(self):
        np = self.np
        for part, left in (((5, 6), False), ((9, 10), True)):
            def lowest(model):
                idx = self.indices(model, part)
                return [-float(w[idx][:, 1].max()) for w in self.worlds(model)]
            for model, limit in ((self.old, None), (self.new, 24)):
                h = lowest(model)
                apex = max(h)
                if limit:
                    self.assertLess(apex, limit, part)
                else:
                    self.assertGreater(apex, 30, part)
            # and the swing's height changes by less than the old hop did from tick to tick
            h_old, h_new = lowest(self.old), lowest(self.new)
            self.assertLess(max(abs(h_new[t] - h_new[t - 1]) for t in range(16)), max(abs(h_old[t] - h_old[t - 1]) for t in range(16)))

    def test_planted_toes_do_not_slip_more(self):
        for bone in (6, 10):
            old, new = self.toe_slip(self.old, bone), self.toe_slip(self.new, bone)
            self.assertLessEqual(new[0], old[0] + 0.5, bone)
            self.assertLessEqual(new[1], old[1] + 0.5, bone)

    def test_stance_ticks_keep_their_pose(self):
        old, new = self.frames(self.old), self.frames(self.new)
        for bones, ticks in ((RIGHT, range(5, 13)), (LEFT, [13, 14, 15, 0, 1, 2, 3, 4])):
            for t in ticks:
                for b in bones:
                    self.assertEqual(new[t][b], old[t][b], (b, t))

    def test_floor_and_penetration(self):
        np = self.np
        for model in (self.old, self.new):
            idx = self.indices(model, (5, 6, 9, 10))
            self.assertLess(max(float(w[idx][:, 1].max()) for w in self.worlds(model)), 4)
        total = {}
        for model in (self.old, self.new):
            body = Body(model, self.rig)
            count = 0
            for f in self.frames(model)[:-1]:
                mats, world = body.world(f)
                for name, chain in GROUPS.items():
                    others = tuple(b for k, c in GROUPS.items() if k != name for b in c)
                    count += body.count(mats, world, chain[1:], BODY + others) + body.count(mats, world, chain[:1], others)
            total[id(model)] = count
        self.assertLessEqual(total[id(self.new)], total[id(self.old)])
        self.assertLessEqual(total[id(self.new)], OLD_PENETRATION)

    def test_whole_body_has_no_tick_jump(self):
        before, after = self.steps(self.old), self.steps(self.new)
        self.assertLess(after[1], 2.5)
        self.assertLessEqual(max(after[0]), max(before[0]))

    def test_the_walk_is_not_flatter(self):
        # the body does not move less: the legs' travel over the loop (each foot's lowest part, front to back) is the same
        np = self.np
        for part in ((5, 6), (9, 10)):
            def travel(model):
                idx = self.indices(model, part)
                z = [float(w[idx][:, 2].mean()) for w in self.worlds(model)]
                return max(z) - min(z)
            self.assertAlmostEqual(travel(self.new), travel(self.old), delta=25)


if __name__ == '__main__':
    unittest.main()
