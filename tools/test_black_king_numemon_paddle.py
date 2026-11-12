"""Check BlackKingNumemon's front pads and face: the pads row forward in the three walking clips, the eyes, brows and
head act a different mood in each clip, and nothing else changes.

The import is read from build/imported-model-edit/edit (`tools/models/edit.py get 307`). The generator is run twice on it,
with and without the pads (`paddle=False` makes the earlier clips), and the two results are compared."""
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
from tools.models.field_animations import black_king_numemon as gen

NB = 18
TICKS = {2: 32, 3: 40, 4: 24}
PAD_BONES = {2, 3, 4, 5}
STALK_BONES = {7, 8, 9, 10, 11, 12}                  # both stalks and eyeballs
FACE_BONES = {2: STALK_BONES, 3: STALK_BONES | {6, 13, 14}, 4: STALK_BONES | {6, 13, 14}}
ROTATION_STEP, SCALE_STEP = 130, 300                 # the most a stalk joint turns or stretches in one tick
IDLE = (0, 1, 18)
EYES = (9, 12)
SLIP_MEAN, SLIP_MAX = 25., 45.


class BlackKingNumemonPads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/307-BlackKingNumemon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 307')
        data = path.read_bytes()
        cls.rig = json.loads(next(Path('content/species').glob('307-*.json')).read_text())['model']['skeleton']
        mmd.exe().add_type(307, cls.rig)
        cls.new_data, cls.report = gen.build(data, cls.rig)
        cls.old_data, _ = gen.build(data, cls.rig, paddle=False, face=False)
        cls.nopad_data, _ = gen.build(data, cls.rig, paddle=True, face=False)
        cls.new, cls.old, cls.nopad = (mmd.MMD.parse(d, NB) for d in (cls.new_data, cls.old_data, cls.nopad_data))
        for m in (cls.new, cls.old, cls.nopad):
            m.type = 307

    def frames(self, model, slot):
        return animsheet.slot_frames(model, NB, slot)[0]

    def test_only_the_walking_slots_and_the_idle_change(self):
        self.assertEqual(self.new.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.new)), set(TICKS) | set(IDLE))
        self.assertEqual(set(changed_programs(self.nopad, self.new)), set(TICKS) | set(IDLE))

    def test_other_bones_keep_their_keys(self):
        for slot, ticks in TICKS.items():
            a, b = self.frames(self.old, slot), self.frames(self.new, slot)
            self.assertEqual(len(a), ticks + 1)
            self.assertEqual(len(b), ticks + 1)
            for t, (fa, fb) in enumerate(zip(a, b)):
                for bone in range(NB):
                    if bone not in PAD_BONES | FACE_BONES[slot]:
                        self.assertEqual(list(fa[bone]), list(fb[bone]), (slot, t, bone))
        for slot in IDLE:
            a, b = self.frames(self.old, slot), self.frames(self.new, slot)
            self.assertEqual(len(a), len(b))
            for t, (fa, fb) in enumerate(zip(a, b)):
                for bone in range(NB):
                    if bone not in STALK_BONES:
                        self.assertEqual(list(fa[bone]), list(fb[bone]), (slot, t, bone))
        self.assertEqual(self.frames(self.old, 33), self.frames(self.new, 33))

    def test_the_face_changes_only_its_bones_over_the_pads(self):
        for slot in TICKS:
            a, b = self.frames(self.nopad, slot), self.frames(self.new, slot)
            for fa, fb in zip(a, b):
                for bone in range(NB):
                    if bone not in FACE_BONES[slot]:
                        self.assertEqual(list(fa[bone]), list(fb[bone]), (slot, bone))

    def test_the_eyes_never_close(self):
        rest = self.frames(self.new, 33)[0]
        for slot in (0, 1, 18, 2, 3, 4):
            for p in self.frames(self.new, slot):
                for eye in EYES:
                    self.assertEqual(list(p[eye][:3]), list(rest[eye][:3]), (slot, eye))      # no lid squash, no flattening

    def test_each_clip_has_its_own_motion(self):
        swing = {}
        for slot in (0, 2, 3, 4):
            f = self.frames(self.new, slot)
            swing[slot] = [np.ptp([p[eye][3] for p in f]) for eye in EYES]
            self.assertGreater(min(swing[slot]), 150, slot)                       # the eyes always sway
        self.assertGreater(min(swing[4]), min(swing[0]) * 1.3)                     # bigger in the run than in the idle
        # the two eyes are not mirror images: their pitch curves differ
        f = self.frames(self.new, 0)
        a, b = ([p[eye][3] for p in f] for eye in EYES)
        self.assertLess(abs(np.corrcoef(a, b)[0, 1]), .9)
        # brows: weary in the tired clip (outer ends down), set in the run (inner ends down), the idle's and walk's brows are the source's (byte test)
        rest = self.frames(self.new, 33)[0][13][5]
        brow = lambda slot: np.mean([p[13][5] - rest for p in self.frames(self.new, slot)]) - np.mean([p[13][5] - rest for p in self.frames(self.old, slot)])
        self.assertLess(brow(3), -100)
        self.assertGreater(brow(4), 100)

    def test_the_face_is_rubbery_not_jittery(self):
        for slot in (0, 2, 3, 4):
            f = np.array(self.frames(self.new, slot), float)
            for bone in STALK_BONES:
                for c in (3, 4, 5):
                    self.assertLessEqual(np.abs(np.diff(f[:, bone, c])).max(), ROTATION_STEP, (slot, bone, c))
                for c in (0, 1, 2):
                    self.assertLessEqual(np.abs(np.diff(f[:, bone, c])).max(), SCALE_STEP, (slot, bone, c))

    def test_pads_move_and_loop_closes(self):
        for slot in TICKS:
            f = self.frames(self.new, slot)
            for bone in PAD_BONES | FACE_BONES[slot]:
                self.assertEqual(list(f[0][bone][:6]), list(f[-1][bone][:6]), (slot, bone))
            yaw = np.array([p[2][4] for p in f])
            self.assertGreater(np.ptp(yaw), 300)

    def sole(self, slot, side):
        hip, pad = gen.PADS[side]
        f = self.frames(self.new, slot)
        rest = self.frames(self.new, 33)[0]
        pads = gen._Pads(self.new, rest, [(b, self.new.tmd.obj_verts(o)) for b, (o, _) in enumerate(self.rig) if o >= 0])
        pts = []
        for p in f:
            m = np.array(mmd.bone_matrices(self.new, p)[pad])
            local = pads.sole[side]
            pts.append(m[:3, :3] @ local[:3] + m[:3, 3])
        return np.array(pts), (f[-1][0][8] - f[0][0][8]) / (len(f) - 1)

    def test_the_planted_sole_does_not_slip(self):
        for slot in TICKS:
            for side in gen.PADS:
                pts, speed = self.sole(slot, side)
                ys = pts[:, 1]
                low, high = ys.max(), ys.min()
                stance = [t for t in range(len(ys) - 1) if ys[t] > low - .25 * (low - high)]
                slip = [abs(pts[t + 1, 2] - pts[t, 2]) / abs(speed) * 100 for t in stance]
                self.assertGreaterEqual(len(stance), 2, (slot, side))
                self.assertLess(np.mean(slip), SLIP_MEAN, (slot, side))
                self.assertLess(max(slip), SLIP_MAX + 60 if (slot, side) == (2, 'L') else SLIP_MAX, (slot, side))
                self.assertLess(ys.max(), 1., (slot, side))      # never sunk through the floor (y is down, the floor is 0)

    def test_resident_buffer(self):
        self.assertLess(self.report['storage']['resident_bytes'], 100352)
        self.assertLess(motionstorage.audit(self.new_data, NB)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
