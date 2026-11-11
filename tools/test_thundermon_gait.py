"""Check Thundermon's own idle, walk, condition walk and run on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 252`). Before the change it is
`thundermon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself.
The arms and boots are measured against the real meshes: a point-inside-mesh test of every arm vertex against the ball.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
import motionstorage
from tools.models.field_animations import thundermon_gait as gait, thundermon_face as face

EXPECTED_TIM = 'e535f642b666a3166cd0e01b11f1fbd065c4616d59d789a69ba572d56d92b49a'
EXPECTED = '87dc7b33e52fd640e6a56b6fc8705a7fc261c1499958e2b8ac18a7f9a0d6ad49'
NB = gait.NB
BUFFER = 100352
ARM_PARTS, BOOTS = (4, 5, 7, 8), (10, 12)


def triangles(model, obj):
    out = []
    for prim in model.tmd.objects[obj].prims:
        ids = prim.decode()['verts']
        out.append(ids[:3])
        if len(ids) == 4:
            out.append([ids[1], ids[3], ids[2]])
    return np.array(out)


def inside(points, verts, tris):
    """Parity of ray crossings along three fixed directions, majority vote."""
    a = verts[tris[:, 0]]
    e1, e2 = verts[tris[:, 1]] - a, verts[tris[:, 2]] - a
    votes = np.zeros(len(points), int)
    for d in ((.5773, .3217, .7501), (-.2113, .9012, .3771), (.8203, -.4411, -.3601)):
        d = np.array(d) / np.linalg.norm(d)
        h = np.cross(d, e2)
        det = (e1 * h).sum(1)
        ok = np.abs(det) > 1e-9
        f = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        s = points[:, None, :] - a[None]
        u = f[None] * (s * h[None]).sum(2)
        q = np.cross(s, e1[None])
        v = f[None] * (q * d).sum(2)
        t = f[None] * (q * e2[None]).sum(2)
        votes += ((ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum(1) % 2)
    return votes >= 2


class ThundermonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/252-Thundermon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 252')
        cls.rig = json.loads(next(Path('content/species').glob('252-*.json')).read_text())['model']['skeleton']
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = gait.parse(data, cls.rig)
            data, _ = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        tim = Path('build/imported-model-edit/edit/252-Thundermon.TIM')
        cls.tim0 = mmd.Tim4(tim.read_bytes()) if hashlib.sha256(tim.read_bytes()).hexdigest() == gait.SOURCE_TIM else None
        cls.tim = gait.texture(tim.read_bytes()) if cls.tim0 else tim.read_bytes()
        cls.new = gait.parse(data, cls.rig)
        cls.verts = {b: np.array(cls.new.tmd.obj_verts(o))[:, :3].astype(float) for b, (o, _) in enumerate(cls.rig) if o >= 0}
        cls.ball = triangles(cls.new, cls.rig[1][0])

    def poses(self, slot):
        return animsheet.slot_frames(self.new, NB, slot)[0]

    def world(self, pose, bone):
        m = np.array(mmd.bone_matrices(self.new, pose))[bone]
        return self.verts[bone] @ m[:3, :3].T + m[:3, 3]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_loops_and_ticks(self):
        for slot in gait.SLOTS:
            frames = self.poses(slot)
            self.assertEqual(len(frames) - 1, gait.GAIT[slot]['n'], slot)
            for b in range(1, NB):          # every pose but the root's travel closes on the first
                self.assertEqual(list(frames[0][b]), list(frames[-1][b]), (slot, b))

    def test_idle_keeps_its_length(self):
        self.assertEqual(gait.GAIT[0]['n'], 97)

    def test_speeds_match_the_stride(self):
        for slot in (2, 3, 4):
            g = gait.GAIT[slot]
            root = [f[0][8] for f in self.poses(slot)]
            steps = {root[i] - root[i + 1] for i in range(len(root) - 1)}
            self.assertLessEqual(max(steps) - min(steps), 1, slot)
            self.assertAlmostEqual(-root[-1] / g['n'], g['speed'], delta=.1)
        self.assertLess(gait.GAIT[3]['speed'], gait.GAIT[2]['speed'])
        self.assertLess(gait.GAIT[2]['speed'], gait.GAIT[4]['speed'])

    def test_unhurried_cycles(self):
        # a gait cycle (two steps) is at least this many ticks: the stepping reads as a walk, not scurrying
        for slot, least in ((2, 12), (3, 20), (4, 10)):
            g = gait.GAIT[slot]
            self.assertGreaterEqual(g['n'] // g['cycles'], least, slot)
        self.assertEqual(self.poses(0).__len__() - 1, 97)

    def test_body_sways_and_bounces(self):
        # the ball rocks about the front-to-back axis, twists against the stride and bounces; the amplitudes follow the
        # native Agumon's (chest and head turn 9 to 18 degrees, the pelvis rises 20 to 36 units) at a chibi scale
        least = {2: (9, 6, 9), 3: (9, 3, 9), 4: (5, 6, 9)}
        for slot, (roll, yaw, bounce) in least.items():
            fr = self.poses(slot)[:-1]
            ang = np.array([f[1][3:6] for f in fr]) * 360 / 4096
            span = ang.max(0) - ang.min(0)
            self.assertGreater(span[2], roll, slot)
            self.assertLess(span[2], 25, slot)
            self.assertGreater(span[1], yaw, slot)
            y = [f[1][7] for f in fr]
            self.assertGreater(max(y) - min(y), bounce, slot)
            self.assertLess(max(y) - min(y), 30, slot)

    def test_feet_do_not_slip(self):
        for slot in (2, 3, 4):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / '252.MMD'
                path.write_bytes(self.data)
                mod = animstudio.Model(f'{path}:252:{Path("build/imported-model-edit/edit/252-Thundermon.TIM").resolve()}', slot)
                _, feet = animstudio.metrics(mod)
            for b, ns, n, mean, worst, lift in feet:
                self.assertLess(mean, 15, (slot, b))
                self.assertLess(worst, 50, (slot, b))
                self.assertGreater(lift, 10, (slot, b))

    def test_arms_stay_out_of_the_ball(self):
        for slot in gait.SLOTS:
            for t, pose in enumerate(self.poses(slot)):
                ball = self.world(pose, 1)
                for b in ARM_PARTS:
                    hit = inside(self.world(pose, b), ball, self.ball)
                    self.assertFalse(hit.any(), (slot, t, b))

    def test_boots_do_not_overlap(self):
        tris = {b: triangles(self.new, self.rig[b][0]) for b in BOOTS}
        for slot in gait.SLOTS:
            for t, pose in enumerate(self.poses(slot)):
                a, b = (self.world(pose, k) for k in BOOTS)
                self.assertFalse(inside(a, b, tris[12]).any() or inside(b, a, tris[10]).any(), (slot, t))

    def test_shoulders_sit_on_the_ball(self):
        for slot in gait.SLOTS:
            for pose in self.poses(slot)[:-1]:
                ball = self.world(pose, 1)
                m = np.array(mmd.bone_matrices(self.new, pose))
                for b in (3, 6):
                    # the joint is held in the body's frame at the same place at every tick
                    local = np.linalg.inv(m[1]) @ m[b]
                    self.assertAlmostEqual(abs(local[0, 3]), gait.SHOULDER[0], delta=1.01)
                    self.assertAlmostEqual(local[1, 3], gait.SHOULDER[1], delta=1.01)

    def test_tired_differs_from_the_run(self):
        tired, run = self.poses(3), self.poses(4)
        self.assertNotEqual(len(tired), len(run))
        lift = lambda frames: -min(np.array(mmd.bone_matrices(self.new, f))[12, 1, 3] for f in frames)
        self.assertLess(lift(tired), lift(run))

    def test_resident_buffer(self):
        self.assertLess(motionstorage.require(self.data, NB)['resident_bytes'], BUFFER)


    # ---- the blink
    def moves(self, slot):
        a = self.new.anims.anims[self.new.anims.table[slot]]
        return [(i['frame'], (i['src'], i['size'], i['dst'])) for i in a.instrs if i['op'] == 'tex']

    def test_every_clip_starts_and_ends_with_open_eyes_and_blinks(self):
        rest = face.eye_move(face.OPEN)
        rest = (rest['src'], rest['size'], rest['dst'])
        for slot in gait.SLOTS:
            moves = self.moves(slot)
            self.assertIn(rest, [m for f, m in moves if f == 1], slot)
            self.assertEqual(moves[-1][1], rest, f'slot {slot}: the last face change is not open eyes')
            self.assertEqual({m[2] for _, m in moves}, {rest[2]}, 'only the eyes are animated')
            shut = face.eye_move(face.SHUT)
            self.assertTrue(any(m[0] == (shut['src'][0], shut['src'][1]) for _, m in moves), slot)
            self.assertLessEqual(moves[-1][0], gait.GAIT[slot]['n'], slot)
        self.assertEqual(sum(1 for _, m in self.moves(0) if m[0] == (32, 72)), 2)       # the idle's double blink

    def test_a_blink_is_quick(self):
        rest = face.eye_move(face.OPEN)
        rest = (rest['src'], rest['size'], rest['dst'])
        for slot in gait.SLOTS:
            start = None
            for f, m in self.moves(slot)[1:]:
                if m != rest and start is None:
                    start = f
                elif m == rest:
                    self.assertLessEqual(f - start, 6, slot)          # half shut to open again
                    start = None

    def test_only_the_texture_events_changed(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        plan = dict(gait.FACE)
        try:
            gait.FACE.update({0: face.blink(50), 2: face.blink(3), 3: face.blink(5), 4: face.blink(4)})
            other, _ = gait.build(Path('build/imported-model-edit/edit/252-Thundermon.MMD').read_bytes(), self.rig)
        finally:
            gait.FACE.update(plan)
        other = gait.parse(other, self.rig)
        for slot in gait.SLOTS:
            self.assertEqual(self.poses(slot), animsheet.slot_frames(other, NB, slot)[0])
        self.assertEqual(self.new.tmd.build(), self.old.tmd.build())

    def test_the_frames_lie_in_texels_no_prim_samples(self):
        used = set()
        for obj in self.new.tmd.objects:
            for p in obj.prims:
                d = p.decode()
                if d['uv']:
                    xs, ys = [u for u, v in d['uv']], [v for u, v in d['uv']]
                    used.update((x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1))
        for at in face.EYE_FRAMES:
            self.assertFalse(any((x, y) in used for x in range(at[0], at[0] + face.EYE_SIZE[0])
                                 for y in range(at[1], at[1] + face.EYE_SIZE[1])), at)
        # the frames lie inside the 256x128 slot and do not touch each other or the painted block
        boxes = [face.EYE_AT, *face.EYE_FRAMES]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                self.assertTrue(a[0] + face.EYE_SIZE[0] <= b[0] or b[0] + face.EYE_SIZE[0] <= a[0]
                                or a[1] + face.EYE_SIZE[1] <= b[1] or b[1] + face.EYE_SIZE[1] <= a[1])

    def test_the_texture_changes_only_in_the_eye_frames(self):
        if self.tim0 is None:
            self.skipTest('needs the texture before this change')
        t0, t1 = self.tim0, mmd.Tim4(self.tim)
        self.assertEqual(hashlib.sha256(self.tim).hexdigest(), EXPECTED_TIM)
        self.assertEqual(face._grab(t1, face.EYE_FRAMES[0], face.EYE_SIZE), face._grab(t0, face.EYE_AT, face.EYE_SIZE))
        self.assertEqual(t0.pal, t1.pal)
        for i in range(len(t0.idx)):
            x, y = i % 256, i // 256
            if not any(a[0] <= x < a[0] + 32 and a[1] <= y < a[1] + 28 for a in face.EYE_FRAMES):
                self.assertEqual(t0.idx[i], t1.idx[i], (x, y))

    def test_the_shut_frame_hides_the_eye(self):
        t = mmd.Tim4(self.tim)
        shut = face._grab(t, face.EYE_FRAMES[face.SHUT], face.EYE_SIZE)
        self.assertEqual({v for row in shut for v in row}, {face.BLUE, face.LASH, face.LASH_SOFT})


if __name__ == '__main__':
    unittest.main()
