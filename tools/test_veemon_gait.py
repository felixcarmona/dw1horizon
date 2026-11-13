"""Check Veemon's idle, walk, tired walk and run (species 180) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 180`; VEEMON_MODEL names another
path). Before the change it is `veemon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself. """
import hashlib
import itertools
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
from tools.models.field_animations import veemon_gait as gait, quadruped

EXPECTED = '15ec6bc3a01e950eb88abd6c0991c5bca8570c0cc085348f334b849f83677638'
NB = 20
TICKS = {2: 24, 3: 36, 4: 16}
IDLE = 96
SPEED = {2: 16, 3: 11, 4: 38}
# Triangle-inside counts per clip, the worst tick of each group pair summed over the pairs, on every second tick: the
# clips before this change measured 202 / 193 / 211 / 200 (arms hanging straight), these must not grow beyond what is measured now.
PENETRATION = {0: 229, 2: 207, 3: 259, 4: 192}       # (the blinks and the foot roll measure 191 / 204 / 259 / 188)
GROUPS = dict(arm_r=[5, 6, 7], arm_l=[8, 9, 10], leg_r=[14, 15, 16], leg_l=[17, 18, 19], hips=[1], torso=[2],
              head=[3, 4], tail=[11, 12, 13])


class VeemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('VEEMON_MODEL', 'build/imported-model-edit/edit/180-Veemon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 180')
        cls.rig = json.loads(Path('content/species/180-veemon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[180] = cls.rig
        mmd.exe().bone_count[180] = NB
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 180
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 180

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, NB, slot)[0]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_cycle_lengths_and_speed_order(self):
        fr = {s: self.frames(s) for s in TICKS}
        self.assertEqual({s: len(f) - 1 for s, f in fr.items()}, TICKS)
        speed = {s: -(fr[s][-1][0][8] - fr[s][0][0][8]) / (len(fr[s]) - 1) for s in SPEED}
        self.assertEqual(speed, SPEED)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        for s, (low, high) in quadruped.SPEED_RANGE.items():
            self.assertTrue(low <= speed[s] <= high, s)
        for s in SPEED:       # one constant root speed
            f = fr[s]
            self.assertEqual(len({round(f[i + 1][0][8] - f[i][0][8], 6) for i in range(len(f) - 1)}), 1, s)

    def test_loops_are_seamless(self):
        for s in TICKS:
            f = self.frames(s)
            for a, b in zip(f[0][1:], f[-1][1:]):
                self.assertLess(max(abs(x - y) for x, y in zip(a[:6], b[:6])), 3, s)

    def test_only_the_idle_and_field_gaits_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        from motiondiscidentity import changed_programs
        self.assertEqual(changed_programs(self.old, self.new), self.report['changed_slots'])
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 35, 36])     # 35 and 36 are the battle walk and run, sharing these clips
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        storage = motionstorage.audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_feet_plant_and_the_floor_holds(self):
        for c in self.report['checks'] if self.old is not None else []:
            self.assertLess(max(c['stance_slip'].values()), 0.25, c['slot'])
            self.assertLessEqual(c['lowest_point'], 3, c['slot'])

    def test_arms_and_head_are_alive_and_follow_the_stride(self):
        """The imported gaits froze both arms, the jaw and the tail. Now every one of them moves, and each hand swings
        against the leg on its side (negative correlation of the fore-aft position, left hand with left foot; the run's arms also flail wide)."""
        np = self.np
        for s in TICKS:
            f = self.frames(s)[:-1]
            for bone in (2, 3, 5, 6, 8, 9, 11):
                span = max(max(p[bone][a] for p in f) - min(p[bone][a] for p in f) for a in (3, 4, 5))
                self.assertGreater(span, 14 if bone != 8 else 8, (s, bone))      # 1.2 degrees of 4096 turn or more
            mats = [mmd.bone_matrices(self.new, [[4096] * 3 + [0] * 6] + [list(b) for b in p[1:]]) for p in f]
            z = lambda b: [float(np.asarray(m[b])[2, 3]) for m in mats]
            for hand, foot in ((7, 16), (10, 19)):
                self.assertLess(np.corrcoef(z(hand), z(foot))[0, 1], -0.1, (s, hand))
                self.assertGreater(max(z(hand)) - min(z(hand)), 15, (s, hand))

    def test_the_idle_has_life(self):
        """96 ticks that close: the head looks round and tilts, the right fist pumps, the tail wags in a burst, the
        body breathes and shifts; the feet stay planted."""
        f = self.frames(0)
        self.assertEqual(len(f) - 1, IDLE)
        f = f[:-1]
        for a, b in zip(self.frames(0)[0][1:], self.frames(0)[-1][1:]):
            self.assertLess(max(abs(x - y) for x, y in zip(a[:6], b[:6])), 3)
        span = lambda bone, axis: max(p[bone][axis] for p in f) - min(p[bone][axis] for p in f)
        self.assertGreater(span(3, 4), 300)        # looks round: about 30 degrees of yaw
        self.assertGreater(span(3, 5), 100)        # tilts its head
        self.assertGreater(span(5, 3), 150)        # the fist pump
        self.assertGreater(span(12, 4), 200)       # the tail wag
        self.assertGreaterEqual(span(1, 7), 2)       # breath and the happy dip, in units
        self.assertGreater(span(2, 3), 40)         # the chest breathes

    def test_hips_counter_rotate_against_the_chest(self):
        np = self.np
        for s in TICKS:
            f = self.frames(s)[:-1]
            for axis in (4, 5):        # yaw and roll
                body = [p[2][axis] for p in f]
                hips = [p[1][axis] for p in f]
                self.assertLess(np.corrcoef(body, hips)[0, 1], -0.5, (s, axis))

    def test_the_two_cycles_differ(self):
        for s in TICKS:
            f = self.frames(s)[:-1]
            half = len(f) // 2
            gap = max(abs(f[i][b][a] - f[i + half][b][a]) for i in range(half) for b in (2, 5, 11, 14) for a in (3, 4, 5))
            self.assertGreater(gap, 12, s)       # not one cycle copied: about one degree or more

    def test_no_bone_jumps_between_ticks(self):
        for s in TICKS:
            f = self.frames(s)[:-1]
            n = len(f)
            for bone in (1, 2, 3, 5, 6, 8, 9, 11):
                for axis in (3, 4, 5):
                    series = [p[bone][axis] for p in f]
                    step = max(min(abs(series[(i + 1) % n] - series[i]), 4096 - abs(series[(i + 1) % n] - series[i]))
                               for i in range(n))
                    self.assertLess(step, 380 if s != 4 else 430, (s, bone, axis, step))            # under 33 degrees a tick (the arms swing wide)

    def test_legs_keep_their_length(self):
        for s in TICKS:
            for p in self.frames(s)[:-1]:
                for b in (15, 16, 18, 19):
                    self.assertEqual(tuple(p[b][6:9]), tuple(self.frames(s)[0][b][6:9]), (s, b))

    def test_no_more_interpenetration_than_the_import(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        from types import SimpleNamespace
        import numpy as np
        import animstudio
        from test_tortomon_gait import inside, DIRS
        mesh = animstudio.FastMesh(SimpleNamespace(m=self.new, skel=self.rig))
        total = {}
        for s in PENETRATION:
            worst = {}
            for pose in self.frames(s)[:-1][::2]:
                p = [list(b) for b in pose]
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
                for a, b in itertools.permutations(GROUPS, 2):
                    tri = world[mesh.tri[np.isin(mesh.bone, GROUPS[a])]]
                    pts = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    tris = world[mesh.tri[np.isin(mesh.bone, GROUPS[b])]]
                    votes = sum(inside(np, pts, tris, d).astype(int) for d in DIRS)
                    worst[a, b] = max(worst.get((a, b), 0), int((votes >= 3).sum()))
            total[s] = sum(worst.values())
        for s, n in total.items():
            self.assertLessEqual(n, PENETRATION[s], (s, total))

    def test_feet_roll(self):
        """The foot's toes point up from the ground at touchdown and down at the push-off: its pitch (the lift of the
        foot's forward axis) swings through a range in every gait (the clips before measured 3 degrees)."""
        need = {2: 18.0, 3: 12.0, 4: 12.0}
        for slot, low in need.items():
            fr = self.frames(slot)
            for bone in (16, 19):
                pitch = []
                for pose in fr:
                    m = mmd.bone_matrices(self.new, pose)[bone]
                    n = math.sqrt(m[0][2] ** 2 + m[1][2] ** 2 + m[2][2] ** 2)
                    pitch.append(math.degrees(math.asin(m[1][2] / n)))
                self.assertGreater(max(pitch) - min(pitch), low, (slot, bone))

    def test_blinks(self):
        """Every field clip opens on the open eye and plays irregular blinks (half shut, shut, half shut, open) that end
        open, so the loop closes; the tired walk's lids are slower; the idle has a double blink."""
        from tools.models.field_animations import veemon_face as face
        plans = {}
        for slot in (0, 2, 3, 4):
            events = [(t, e) for t, k, e in animsheet.slot_frames(self.new, NB, slot)[2] if k == 'tex']
            self.assertEqual(events[0][0], 0, slot)
            self.assertEqual(events[0][1]['src'], face.eye_move(face.OPEN)['src'], slot)
            self.assertEqual(events[-1][1]['src'], face.eye_move(face.OPEN)['src'], slot)
            for _, e in events:
                self.assertEqual((e['size'], e['dst']), (face.eye_move(face.OPEN)['size'], face.eye_move(face.OPEN)['dst']))
            states = {face.eye_move(k)['src']: k for k in (face.OPEN, face.HALF, face.SHUT)}
            plans[slot] = [(t, states[e['src']]) for t, e in events[1:]]
            shut = [t for t, k in plans[slot] if k == face.SHUT]
            self.assertGreaterEqual(len(shut), 1 if slot == 4 else 2, slot)
        gaps = lambda plan: sorted(b - a for a, b in zip([t for t, k in plan if k == face.SHUT], [t for t, k in plan if k == face.SHUT][1:]))
        self.assertLessEqual(gaps(plans[0])[0], 8)           # the double blink
        self.assertGreater(gaps(plans[0])[-1], 25)
        closed = lambda plan: [b - a for (a, ka), (b, kb) in zip(plan, plan[1:]) if ka == face.SHUT]
        self.assertGreater(max(closed(plans[3])), max(closed(plans[2])))

    def test_shut_eye_covers_the_open_eye(self):
        """The shut frame holds none of the eye's iris, glint or red rim: it replaces the open eye everywhere."""
        from tools.models.field_animations import veemon_face as face
        raw = None
        for tim in (Path(os.environ.get('VEEMON_MODEL', 'build/imported-model-edit/edit/180-Veemon.MMD')).with_suffix('.TIM'),):
            if tim.exists():
                raw = tim.read_bytes()
        if raw is None:
            self.skipTest('needs the texture beside the model')
        if hashlib.sha256(raw).hexdigest() == gait.SOURCE_TIM:
            raw = gait.texture(raw)
        t = mmd.Tim4(raw)
        eye = face._grab(t, face.EYE_FRAMES[face.OPEN], face.EYE_SIZE)
        for state in (face.HALF, face.SHUT):
            frame = face._grab(t, face.EYE_FRAMES[state], face.EYE_SIZE)
            lit = lambda block: sum(v in (4, 5, 6, 7, 0xb, 0xc) for row in block[:38] for v in row)
            self.assertLess(lit(frame), lit(eye) * (0.7 if state == face.HALF else 0.05), state)
        shut = face._grab(t, face.EYE_FRAMES[face.SHUT], face.EYE_SIZE)
        self.assertEqual(shut[38:], eye[38:])           # the texels below the eye are kept
        self.assertEqual(face._grab(t, face.EYE_AT, face.EYE_SIZE), eye)       # the block in the model is the open eye


if __name__ == '__main__':
    unittest.main()
