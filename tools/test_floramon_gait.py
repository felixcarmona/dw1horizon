"""Floramon's (273) calm idle, loose walk and the blink in every field clip (floramon_gait.py), on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 273`) and paced with pace.py, which is
what the generator follows; the tests are skipped when that folder is missing.
"""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import floramon_gait as gait, pace

ROOT = Path(__file__).resolve().parents[1]
EDIT = ROOT / 'build/imported-model-edit/edit'
NB = gait.NB
BUFFER = 100352
SK = [tuple(b) for b in json.loads((ROOT / 'content/species/273-floramon.json').read_text())['model']['skeleton']]


def _turn(d):
    return ((d + 2048) % 4096) - 2048


def ranges(model, slot):
    """Per bone: (largest range of a rotation channel, its largest step per tick) in 1/4096 turns."""
    frames = animsheet.slot_frames(model, NB, slot)[0]
    n = len(frames) - 1
    out = {}
    for b in range(1, NB):
        rng, step = 0, 0
        for c in (3, 4, 5):
            u = [frames[0][b][c]]
            for t in range(1, n + 1):
                u.append(u[-1] + _turn(frames[t][b][c] - u[-1]))
            rng = max(rng, max(u) - min(u))
            step = max(step, max(abs(u[i + 1] - u[i]) for i in range(n)))
        out[b] = (rng, step)
    return out


def played(model, slot, ticks):
    animation = model.anims.anims[model.anims.table[slot]]
    player = mmd.AnimPlayer(animation, NB, slot)
    out = []
    for _ in range(ticks + 1):
        assert player.tick(stop_at_infinite_loop=False)
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = list(player.root)
        out.append(pose)
    return out


def parse(data):
    mmd.exe().skeleton[273] = SK
    mmd.exe().bone_count[273] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = 273
    return model


@unittest.skipUnless((EDIT / '273-Floramon.MMD').exists(), 'run tools/models/edit.py get 273 first')
class FloramonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import edit
        edit.crmath.install()
        edit.pysum.install()
        cls.edit = edit
        rows = json.loads(pace.MANIFEST.read_text())
        del rows['273']['after_generator']
        cls.manifest = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(rows, cls.manifest)
        cls.manifest.close()
        real = pace.MANIFEST
        pace.MANIFEST = Path(cls.manifest.name)
        try:
            paced, _ = pace.build((EDIT / '273-Floramon.MMD').read_bytes(), SK)      # the pace pass alone
        finally:
            pace.MANIFEST = real
        cls.paced_bytes = paced
        cls.before = parse(paced)
        cls.out, cls.report = gait.build(paced, SK)
        cls.after = parse(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.edit.crmath.uninstall()
        cls.edit.crmath.clear()
        cls.edit.pysum.uninstall()
        Path(cls.manifest.name).unlink()

    def test_the_pace_row_names_the_generator_and_the_input_is_pinned(self):
        import hashlib
        rows = json.loads(pace.MANIFEST.read_text())
        self.assertEqual(rows['273']['after_generator'], 'tools.models.field_animations.floramon_gait')
        self.assertEqual(hashlib.sha256(self.paced_bytes).hexdigest(), gait.SOURCE)  # the pace pass's output, the layer's input
        full, _ = pace.build((EDIT / '273-Floramon.MMD').read_bytes(), SK)            # the registered path
        self.assertEqual(full, self.out)

    def test_changed_slots_and_sharing(self):
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4])
        shared = {r['slot']: r.get('shared_by') for r in self.report['checks']}
        self.assertEqual(shared[4], [4])
        t = self.after.anims.table
        self.assertEqual(t[33], self.before.anims.table[33])          # the old idle stays on slot 33
        self.assertNotEqual(t[0], t[33])
        for slot in (1, 14, 15, 16, 17, 18, 34, 33):
            self.assertEqual(played(self.before, slot, 40), played(self.after, slot, 40), slot)

    def test_run_poses_and_root_are_identical(self):
        for slot in (4, 36):       # 36 is the source's own rebuilt battle run (battle-rebuilds.json): untouched
            self.assertEqual(played(self.before, slot, 60), played(self.after, slot, 60), slot)

    def test_tired_walk_droops_the_head_and_keeps_the_rest(self):
        old, new = played(self.before, 3, 84), played(self.after, 3, 84)
        for t in range(len(old)):
            for bone in range(NB):
                if bone not in (2, 3):                                  # chest and head are the only bones that change
                    self.assertEqual(old[t][bone], new[t][bone], (t, bone))
        self.assertEqual(len(animsheet.slot_frames(self.before, NB, 3)[0]), len(animsheet.slot_frames(self.after, NB, 3)[0]))
        rig = gait.Rig(self.before, SK)

        def pitch(model):
            # the head's forward axis elevation: in this rig y points down, so a head hanging down has a NEGATIVE value here
            out = []
            for f in animsheet.slot_frames(model, NB, 3)[0]:
                forward = rig.world([[float(v) for v in b] for b in f])[3, :3, :3] @ np.array([0, 0, 1.])
                out.append(math.degrees(math.asin(float(forward[1]))))
            return out
        before, after = pitch(self.before), pitch(self.after)
        self.assertLessEqual(sum(after) / len(after) - sum(before) / len(before), -20)    # hangs about 25 degrees lower
        self.assertGreater(max(after) - min(after), 6)                  # and bobs slowly
        self.assertLessEqual(max(abs(after[t + 1] - after[t]) for t in range(len(after) - 1)), 5)
        # in world space (y down): the head's frontmost and highest vertices sit LOWER than before, relative to the chest,
        # and the crown has moved forward (-z)
        hv = np.array(self.before.tmd.obj_verts(SK[3][0]))[:, :3]
        front, crown = np.argmin(hv[:, 2]), np.argmin(hv[:, 1])
        for t in (0, 10, 20, 30):
            marks = []
            for model in (self.before, self.after):
                w = rig.world([[float(v) for v in b] for b in animsheet.slot_frames(model, NB, 3)[0][t]])
                p = hv @ w[3, :3, :3].T + w[3, :3, 3]
                marks.append((p[front] - w[2, :3, 3], p[crown] - w[2, :3, 3]))
            self.assertGreaterEqual(marks[1][0][1] - marks[0][0][1], 25, t)      # the face is 25+ units lower
            self.assertGreaterEqual(marks[1][1][1] - marks[0][1][1], 5, t)      # the crown is lower too
            self.assertLessEqual(marks[1][1][2] - marks[0][1][2], -25, t)        # and forward
        frames = animsheet.slot_frames(self.after, NB, 3)[0]
        for b in range(1, NB):
            for c in range(3, 6):
                self.assertLessEqual(abs(_turn(frames[-1][b][c] - frames[0][b][c])), abs(_turn(
                    animsheet.slot_frames(self.before, NB, 3)[0][-1][b][c] - animsheet.slot_frames(self.before, NB, 3)[0][0][b][c])) + 1, (b, c))

    def test_idle_is_calm_and_closed(self):
        old, new = ranges(self.before, 0), ranges(self.after, 0)
        self.assertLess(sum(r for r, _ in new.values()), .7 * sum(r for r, _ in old.values()))
        self.assertLess(sum(s for _, s in new.values()), .6 * sum(s for _, s in old.values()))
        for b, (r, s) in new.items():
            self.assertLessEqual(r, 500 if b in (7, 11) else 300, b)      # no limb swings: the curled tendrils' tips aside, 26 degrees
            self.assertLessEqual(s, 40, b)
        self.assertGreater(sum(r for r, _ in new.values()), 1500)    # alive, not frozen
        frames = animsheet.slot_frames(self.after, NB, 0)[0]
        self.assertEqual(len(frames) - 1, gait.IDLE_TICKS)
        for b in range(1, NB):
            for c in range(3, 6):
                self.assertLessEqual(abs(_turn(frames[-1][b][c] - frames[0][b][c])), 1, (b, c))
        # a loop is smooth: no tick moves a bone by more than a few times the median step
        play = played(self.after, 0, 2 * gait.IDLE_TICKS)
        for b in range(1, NB):
            steps = [max(abs(_turn(play[t + 1][b][c] - play[t][b][c])) for c in (3, 4, 5)) for t in range(len(play) - 1)]
            self.assertLessEqual(max(steps), 40, b)

    def test_walk_differs_keeps_travel_and_is_planted(self):
        old = animsheet.slot_frames(self.before, NB, 2)[0]
        new = animsheet.slot_frames(self.after, NB, 2)[0]
        self.assertEqual(len(new) - 1, gait.WALK_TICKS)             # two hops of 13 ticks (the run's hops are 10)
        self.assertEqual({round(new[t + 1][0][8] - new[t][0][8]) for t in range(len(new) - 1)}, {-gait.WALK_SPEED})  # constant root travel
        speed = abs(new[-1][0][8] - new[0][0][8]) / (len(new) - 1)
        self.assertTrue(15 <= speed <= 20)          # native walk range, above the condition walk (10.7), under the run (39)
        step = {round(new[t + 1][0][8] - new[t][0][8]) for t in range(len(new) - 1)}
        self.assertLessEqual(len(step), 2)
        self.assertNotEqual(old[5][1:], new[5][1:])
        # the pelvis hops: a rise in flight of over half of the run's (61 units), a smooth arc
        y = [f[1][7] for f in new]
        run_y = [f[1][7] for f in animsheet.slot_frames(self.after, NB, 4)[0]]
        self.assertTrue(.5 * (max(run_y) - min(run_y)) <= max(y) - min(y) <= .7 * (max(run_y) - min(run_y)))
        self.assertLessEqual(max(abs(y[t + 1] - y[t]) for t in range(len(y) - 1)), 16)
        # two hops a loop, each a minimum and a maximum
        self.assertEqual(y[:13], y[13:26])
        feet = pace._feet(self.before, SK)
        before_slip = pace.slip(self.before, [[list(b) for b in p] for p in old], feet)
        after_slip = pace.slip(self.after, [[list(b) for b in p] for p in new], feet)
        self.assertLess(after_slip[0], 25)
        self.assertLess(after_slip[0], before_slip[0] / 2)
        # loop closes
        for b in range(1, NB):
            for c in range(3, 6):
                self.assertLessEqual(abs(_turn(new[-1][b][c] - new[0][b][c])), 2, (b, c))
        # loose: second harmonics and lag, no sinusoid of one phase: arm, flower and tendril peak at different ticks
        peaks = []
        for b in (4, 6, 7):
            v = [new[t][b][3] for t in range(len(new) - 1)]
            peaks.append(max(range(len(v)), key=v.__getitem__))
        self.assertEqual(len(set(peaks)), 3)
        # no tick jumps beyond about 2.5 times the median of the vertex speeds
        verts = {b: np.array(self.after.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(SK) if o >= 0}
        speeds = []
        prev = None
        for pose in played(self.after, 2, 56):
            still = [list(v) for v in pose]
            still[0] = [4096] * 3 + still[0][3:6] + [0, 0, 0]
            w = np.array(mmd.bone_matrices(self.after, still))
            pts = np.concatenate([verts[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in sorted(verts)])
            if prev is not None:
                speeds.append(float(np.linalg.norm(pts - prev, axis=1).mean()))
            prev = pts
        self.assertLessEqual(max(speeds), 2.5 * float(np.median(speeds)))

    def test_head_rocks_side_to_side(self):
        rig = gait.Rig(self.before, SK)

        def roll(model):
            out = [math.degrees(math.atan2(w[1, 0], w[0, 0])) for w in
                   (rig.world([[float(v) for v in b] for b in f])[3, :3, :3] for f in animsheet.slot_frames(model, NB, 2)[0])]
            return [((a - out[0] + 180) % 360) - 180 for a in out]
        before, after = roll(self.before), roll(self.after)
        self.assertGreaterEqual(max(after) - min(after), 24)          # about +-13 degrees, once a loop (one side per skip)
        self.assertLessEqual(max(after) - min(after), 32)
        self.assertGreater(max(after) - min(after), 2 * (max(before) - min(before)))
        self.assertLessEqual(max(abs(after[t + 1] - after[t]) for t in range(len(after) - 1)), 6)   # smooth

    def test_every_clip_blinks_from_and_to_open_eyes(self):
        open_ = gait.eye_move('open')
        for slot, loops in ((0, 1), (2, 1), (3, 1), (4, 1)):
            program = self.after.anims.anims[self.after.anims.table[slot]]
            tex = [i for i in program.instrs if i['op'] == 'tex']
            self.assertGreaterEqual(len(tex), 4, slot)
            self.assertEqual({k: tex[0][k] for k in ('src', 'size', 'dst')}, {k: open_[k] for k in ('src', 'size', 'dst')})
            self.assertEqual(tex[0]['frame'], 1)
            self.assertEqual({k: tex[-1][k] for k in ('src', 'size', 'dst')}, {k: open_[k] for k in ('src', 'size', 'dst')})
            self.assertLess(tex[-1]['frame'], program.frame_count)
        # idle: a blink every 2 to 3.5 seconds (20 ticks a second) and one double blink per loop
        shut = sorted(i['frame'] for i in self.after.anims.anims[self.after.anims.table[0]].instrs
                      if i['op'] == 'tex' and i['src'] == gait.EYE_FRAMES['shut'])
        self.assertEqual(len(shut), 4)
        gaps = [b - a for a, b in zip(shut, shut[1:])] + [shut[0] + gait.IDLE_TICKS - shut[-1]]
        self.assertEqual(sum(1 for g in gaps if g < 12), 1)           # one double blink
        for g in gaps:
            self.assertTrue(g < 12 or 40 <= g <= 70, g)               # otherwise 2 to 3.5 seconds apart

    def test_buffer(self):
        report = motionstorage.require(self.out, NB)
        self.assertLess(report['resident_bytes'], BUFFER)
        self.assertEqual(report['resident_bytes'], self.report['storage']['resident_bytes'])

    def test_mesh_skeleton_unchanged(self):
        self.assertEqual(self.before.tmd.build(), self.after.tmd.build())


class EyeFrames(unittest.TestCase):
    """The blink's three frames sit in texels no face samples (exact UV-triangle raster, margin 1)."""

    @unittest.skipUnless((EDIT / '273-Floramon.TIM').exists() and (EDIT / '273-Floramon.MMD').exists(), 'run tools/models/edit.py get 273 first')
    def test_frames_are_in_unsampled_texels(self):
        model = parse((EDIT / '273-Floramon.MMD').read_bytes())
        sampled = np.zeros((128, 256), bool)
        for obj in model.tmd.objects:
            for prim in obj.prims:
                d = prim.decode()
                uv = d['uv']
                if not uv:
                    continue
                tris = [uv[:3]] if len(uv) == 3 else [uv[:3], [uv[1], uv[3], uv[2]]]
                for tri in tris:
                    xs, ys = [p[0] for p in tri], [p[1] for p in tri]
                    for y in range(max(0, min(ys) - 1), min(127, max(ys) + 1) + 1):
                        for x in range(max(0, min(xs) - 1), min(255, max(xs) + 1) + 1):
                            if _near(tri, x + .5, y + .5):
                                sampled[y, x] = True
        for state in ('half', 'shut'):
            x, y = gait.EYE_FRAMES[state]
            w, h = gait.EYE_SIZE
            self.assertFalse(sampled[y:y + h, x * 4:(x + w) * 4].any(), state)
        x, y = gait.EYE_FRAMES['open']
        self.assertFalse(sampled[y:y + 28, x * 4:x * 4 + 56].any())
        # the target of the moves is the painted eyes at (0, 0)
        self.assertTrue(sampled[0:28, 0:56].any())


def _near(tri, px, py, margin=1.0):
    """True when (px, py) is inside the triangle grown by `margin` texels."""
    (x0, y0), (x1, y1), (x2, y2) = tri
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if area == 0:
        return True
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y1)), ((x1, y1), (x2, y2)), ((x2, y2), (x0, y0))):
        edge = ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) * (1 if area > 0 else -1)
        length = math.hypot(bx - ax, by - ay) or 1
        if edge / length < -margin:
            return False
    return True


if __name__ == '__main__':
    unittest.main()
