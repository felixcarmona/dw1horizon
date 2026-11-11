"""Valkyrimon's field clips keep the original timing and root travel, with a calmer carriage and the limbs cleared of the body.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 255`). Before the change it is
`valkyrimon_limbs.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that compare with the original are skipped.
"""
import copy
import math
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
import retarget as R
from tools.models.field_animations import valkyrimon_limbs as limbs

EXPECTED = '6ff402e2f561835604ff98451d202e1096d6e456acbd86d60374d5703f89f94c'
CHANGED = {1, 5, 6, 7, 9, 10, 11, 18, 19, 20, 21, 22, 23, 24}   # the bones the generator touches in the walk, tired walk and run
IDLE = {1, 2, 3, 4, 5, 6, 9, 10, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25, 28}   # and in the idle (it breathes, looks, sways)
LOOSE = {1: (6, 7), 24: (6, 7, 8)}                   # translation channels that may move: the pelvis' sway and rise, the cloth's hanging point
TURN_LIMIT = 4096 * 90 // 360                        # no bone ends up more than 90 degrees from where it was (1/4096 turn)
PELVIS_BASE = 61                                      # the thigh tops sit inside the hip mesh in the pose the model is built in


class ValkyrimonLimbs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/255-Valkyrimon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 255')
        cls.rig = json.loads(Path('content/species/255-valkyrimon.json').read_text())['model']['skeleton']
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == limbs.SOURCE:
            cls.old = limbs._parse(data, cls.rig)
            data, cls.report = limbs.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = limbs._parse(data, cls.rig)
        cls.body = limbs.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 30, slot)

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_field_clips_change_and_the_mesh_does_not(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(self.new.anims.table[33], self.old.anims.table[33])      # slot 33 keeps the old idle program

    def test_timing_is_the_original(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        for slot, ticks in {0: 126, 2: 25, 3: 29, 4: 17}.items():
            a, loop_a, events_a = self.frames(slot, self.old)
            b, loop_b, events_b = self.frames(slot)
            self.assertEqual((len(a), len(b)), (ticks, ticks))
            self.assertEqual(loop_a, loop_b)
            self.assertEqual(events_a, events_b)                                  # the footstep sounds
            for p, q in zip(a, b):
                self.assertEqual(p[0], q[0], slot)                                 # root: rotation and travel, every tick

    def test_only_the_arms_the_legs_and_the_pelvis_height_differ(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        worst = {}
        for slot in (0, 2, 3, 4):
            a, _, _ = self.frames(slot, self.old)
            b, _, _ = self.frames(slot)
            for p, q in zip(a, b):
                for bone in range(1, 30):
                    if p[bone] == q[bone]:
                        continue
                    self.assertIn(bone, IDLE if slot == 0 else CHANGED, (slot, bone))
                    keep = [c for c in range(9) if c not in LOOSE.get(bone, ())]
                    self.assertEqual([p[bone][c] for c in keep if c > 5 or c < 3], [q[bone][c] for c in keep if c > 5 or c < 3])
                    if bone == 1:
                        self.assertEqual(p[bone][3:6], q[bone][3:6])               # the pelvis only rises, falls and sways
                        continue
                    turn = max(abs(x - y) for x, y in zip(p[bone][3:6], q[bone][3:6])) % 4096
                    worst[bone] = max(worst.get(bone, 0), min(turn, 4096 - turn))
        self.assertTrue(worst)
        self.assertLess(max(worst.values()), TURN_LIMIT, worst)

    def pose_world(self, pose):
        q = copy.deepcopy(pose)
        q[0] = [4096] * 3 + [0] * 6
        return R.world_pos(self.rig, q)

    def test_the_feet_keep_their_ground_contact_and_the_carriage_is_calmer(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        calmer = {2: (.7, .8), 3: (.95, .9), 4: (.8, .8)}                          # bob and knee lift at most these shares
        for slot, (bob_share, lift_share) in calmer.items():
            a = [self.pose_world(p) for p in self.frames(slot, self.old)[0]]
            b = [self.pose_world(p) for p in self.frames(slot)[0]]
            for ankle in (20, 23):                  # the ankles stay on the same track, the feet a little wider apart
                for u, v in zip(a, b):
                    self.assertLess(math.dist(u[ankle], v[ankle]), 32, (slot, ankle))
                    self.assertLess(abs(u[ankle][2] - v[ankle][2]), 3, (slot, ankle))
            for bones in ((18, 19, 20), (21, 22, 23)):
                self.assertLess(max(math.dist(u[bones[1]], v[bones[1]]) for u, v in zip(a, b)), 40)
            span = lambda w, i: max(x[i][1] for x in w) - min(x[i][1] for x in w)
            self.assertLess(span(b, 1), bob_share * span(a, 1) + 1, slot)
            lift = lambda w, i: max(x[i][1] for x in w) - min(x[i][1] for x in w)
            self.assertLess(lift(b, 19), lift_share * lift(a, 19) + 1, slot)
            # the pelvis never drops below the lowest the original reached, so the legs never get longer than they are
            self.assertLessEqual(max(x[1][1] for x in b), max(x[1][1] for x in a) + 1)

    def test_the_idle_keeps_its_feet_planted(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        a = [self.pose_world(p) for p in self.frames(0, self.old)[0]]
        b = [self.pose_world(p) for p in self.frames(0)[0]]
        for ankle in (20, 23):
            self.assertLess(max(math.dist(u[ankle], v[ankle]) for u, v in zip(a, b)), 1.5)

    def test_the_forearms_are_opened_and_the_arms_trail_the_legs(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        def flexion(frames, bone):
            return sum(((p[bone][3] * 360 / 4096) % 360) - 360 for p in frames) / len(frames)
        for slot in (2, 4):
            a = self.frames(slot, self.old)[0]
            b = self.frames(slot)[0]
            for bone in (6, 10):
                self.assertGreater(flexion(b, bone), flexion(a, bone) + 15, (slot, bone))
        # the shoulders' swing of the walk is wider than before, as the arc is larger and looser
        a = self.frames(2, self.old)[0]
        b = self.frames(2)[0]
        for bone in (5, 9):
            width = lambda f: max(p[bone][3] for p in f) - min(p[bone][3] for p in f)
            self.assertGreater(width(b), 1.1 * width(a))

    def test_loops_close_and_no_bone_moves_faster_than_before(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        for slot in (0, 2, 3, 4):
            a = self.frames(slot, self.old)[0]
            b = self.frames(slot)[0]
            for bone in (IDLE if slot == 0 else CHANGED) - {1, 24}:   # the cloth's turn mirrors the thigh's: its world pose is smooth
                for k in (3, 4, 5):
                    step = lambda f: max(abs(f[(t + 1) % len(f)][bone][k] - f[t][bone][k]) for t in range(len(f)))   # wraps the loop
                    self.assertLessEqual(step(b), 1.5 * step(a) + 4096 * 8 // 360, (slot, bone, k))

    def test_no_limb_goes_through_the_body(self):
        for slot in (0, 2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[0]):
                rep = self.body.report(pose)
                self.assertEqual((rep['legs'], rep['armR'], rep['armL']), (0, 0, 0), (slot, tick, rep))
                self.assertLessEqual(rep['pelvis'], PELVIS_BASE, (slot, tick))

    def test_the_original_did_go_through_the_body(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        body = limbs.Body(self.old, self.rig)
        worst = max(body.report(p, ('armR',))['armR'] for p in self.frames(2, self.old)[0])
        self.assertGreater(worst, 100)

    def test_boots_still_clear_the_floor_at_ticks_and_renderer_thirds(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)[0]
            for a, b in zip(frames, frames[1:] + [frames[0]]):
                for alpha in (0, 1365, 2730):
                    pose = interpolate_pose(a, b, alpha)
                    pose = copy.deepcopy(pose)
                    pose[0] = [4096] * 3 + [0] * 6
                    mats = mmd.bone_matrices(self.new, pose)
                    low = max(sum(mats[boot][1][i] * v[i] for i in range(3)) + mats[boot][1][3]
                              for boot in (20, 23) for v in self.new.tmd.obj_verts(self.rig[boot][0]))
                    self.assertLess(low, 4, (slot, alpha, low))      # the original idle already stands 3.6 units off the ground

    def world_gap(self, pose, bones_a, bones_b):
        mesh = self.body.mesh
        w = self.body.world(pose)[1]
        a = w[mesh.tri[np.isin(mesh.bone, bones_a)]].reshape(-1, 3)[::2]
        b = w[mesh.tri[np.isin(mesh.bone, bones_b)]].reshape(-1, 3)[::2]
        return float(np.sqrt(((a[:, None] - b[None]) ** 2).sum(2)).min())

    def test_the_legs_stay_apart_through_the_whole_stride(self):
        # lateral distance between the two ankles and the two knees at the closest tick: the original walk and run
        # brought the feet to 32-33 units (the thigh tops are 42 apart); a natural stance keeps them at least 55 apart
        for slot, ankle_min, knee_min in ((2, 55, 38), (3, 55, 43), (4, 55, 38)):
            worst_a = worst_k = 1e9
            for pose in self.frames(slot)[0]:
                w = self.pose_world(pose)
                worst_a = min(worst_a, abs(w[23][0] - w[20][0]))
                worst_k = min(worst_k, abs(w[22][0] - w[19][0]))
            self.assertGreaterEqual(worst_a, ankle_min, (slot, 'ankles'))
            self.assertGreaterEqual(worst_k, knee_min, (slot, 'knees'))
        if self.old is not None:
            for slot in (2, 4):
                before = min(abs(self.pose_world(p)[23][0] - self.pose_world(p)[20][0]) for p in self.frames(slot, self.old)[0])
                self.assertLess(before, 35)

    def cloth_swing(self, model, slot):
        mesh = limbs.Body(model, self.rig).mesh
        body = limbs.Body(model, self.rig)
        worlds = []
        for pose in self.frames(slot, model)[0]:
            mats, w = body.world(pose)
            chest = np.array(mats[2], float)
            chest = chest if chest.shape == (4, 4) else np.vstack([chest, [0, 0, 0, 1]])
            h = np.hstack([w, np.ones((len(w), 1))])
            worlds.append((h @ np.linalg.inv(chest).T)[:, :3])
        worlds = np.array(worlds)
        swing = {}
        for bone in (13, 14, 15, 16, 17, 24, 25, 29):
            pts = worlds[:, mesh.tri[mesh.bone == bone].reshape(-1)]
            swing[bone] = float(np.linalg.norm(pts - pts.mean(0), axis=2).max())
        return swing

    def test_the_cloth_stays_with_the_body(self):
        # the cloth hanging from the left thigh (24, 25) rode the whole leg and swung 70 to 190 units from the chest;
        # it now hangs from the pelvis. Every other cloth piece keeps its original swing.
        limits = {2: 75, 3: 65, 4: 110}
        for slot, limit in limits.items():
            now = self.cloth_swing(self.new, slot)
            self.assertLess(max(now[24], now[25]), limit, (slot, now))
            if self.old is not None:
                before = self.cloth_swing(self.old, slot)
                for bone in (13, 14, 15, 16, 17, 29):
                    self.assertLessEqual(now[bone], before[bone] + 1, (slot, bone))
                for bone in (24, 25):
                    self.assertLess(now[bone], .85 * before[bone], (slot, bone))

    def test_the_cloth_does_not_sink_into_the_body(self):
        for slot in (2, 3, 4):
            worst = 0
            for pose in self.frames(slot)[0]:
                mats, w = self.body.world(pose)
                worst = max(worst, self.body.count(self.body.mesh, mats, w, (24, 25), (1, 2, 18, 19, 21, 22, 26)))
            self.assertLessEqual(worst, 10, slot)             # the original already had 4 to 6 of its 8 vertices in the thigh

    def test_the_idle_is_alive(self):
        # the original idle held still for its first third and then made one slow lean; it now breathes, looks around and
        # sways all the time. Ranges inside the held stretch (ticks 0 to 38), in degrees and units
        held = self.frames(0)[0][:39]
        deg = 360 / 4096
        span = lambda bone, ch: (max(f[bone][ch] for f in held) - min(f[bone][ch] for f in held)) * (deg if 3 <= ch <= 5 else 1)
        self.assertGreaterEqual(span(2, 3), 3.5)            # chest
        self.assertGreaterEqual(span(5, 3) + span(9, 3), 6)  # shoulders
        self.assertGreaterEqual(span(4, 4), 5)              # head turns
        self.assertGreaterEqual(span(1, 6), 3)              # weight shift
        self.assertGreaterEqual(span(14, 3), 3.5)             # wings trail
        if self.old is not None:
            old = self.frames(0, self.old)[0][:39]
            self.assertLess(max(f[2][3] for f in old) - min(f[2][3] for f in old), 3.5 / deg)

    def test_storage_fits_the_resident_buffer(self):
        storage = motionstorage.audit(self.data, 30)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
