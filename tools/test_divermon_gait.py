"""Check Divermon's idle, walk, tired walk and run (species 304) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 304`; DIVERMON_MODEL names another
path). Before the change it is `divermon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself and the checks that need the old clips are skipped.

Divermon: upper body 1, right arm 2-4, left arm 5-7 (the harpoon), head 8, ears 9 and 13, tank 10-12, hips 14,
tail 15-17, left leg 18-21 (hip, knee, heel, toes), right leg 22-25.
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
from tools.models.field_animations import divermon_face as face
from tools.models.field_animations import divermon_gait as gait

EXPECTED = 'd011916e654e61167c661338a370ab8bf93e69b7add0c9526fc0f7348f084348'
EXPECTED_TIM = '8537831b18b55452cab7038f2da989c2a267ecf6d3129e34c745483d833236be'
BONES = 26
TICKS = {2: 32, 3: 36, 4: 24}              # two strides each: no two look alike
CYCLE = {2: 16, 3: 18, 4: 12}
IDLE_TICKS = 240
SPEED = {2: 18, 3: 12, 4: 36}
TOES = {'LH': 21, 'RH': 25}
LEGS = {'LH': (18, 19, 20, 21), 'RH': (22, 23, 24, 25)}
EARS = {9: -1, 13: 1}
LEG_BONES = {18, 19, 20, 22, 23, 24}


class DivermonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('DIVERMON_MODEL', 'build/imported-model-edit/edit/304-Divermon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 304')
        cls.rig = json.loads(Path('content/species/304-divermon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[304] = cls.rig
        mmd.exe().bone_count[304] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 304
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        tim = path.with_suffix('.TIM')
        cls.tim0 = None
        if tim.exists():
            raw = tim.read_bytes()
            if hashlib.sha256(raw).hexdigest() == gait.SOURCE_TIM:
                cls.tim0, raw = mmd.Tim4(raw), gait.texture(raw)
            cls.tim = raw
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 304

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def points(self, pose, model=None):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return [self.np.array(m, float)[:3, 3] for m in mmd.bone_matrices(model or self.new, p)]

    def feet(self, slot):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        rows = []
        for pose in self.frames(slot):
            p = copy.deepcopy(pose)
            p[0] = [4096] * 3 + [0] * 6
            mats = mmd.bone_matrices(self.new, p)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(self.np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_their_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4, 33, 35, 36])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_breathes_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))
        rows = self.feet(0)
        for name in TOES:
            for axis in (0, 1, 2):
                values = [r[name][axis] for r in rows]
                self.assertLess(max(values) - min(values), 4, (name, axis))
        height = [f[1][7] for f in frames]
        self.assertGreaterEqual(max(height) - min(height), 4)           # the chest rises and falls
        for b, least in ((8, 4), (1, 4), (4, 4)):
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

    def test_loops_are_seamless(self):
        for slot in TICKS:
            first, last = self.frames(slot)[0], self.frames(slot)[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_feet_are_planted_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                stance = [i for i, r in enumerate(rows) if r[name][1] < 8]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_each_foot_points_forward_and_never_turns_sideways(self):
        """The import turned the ankle 77 degrees out; now the sole keeps a 7 degree splay in every tick of every clip."""
        for slot in (0, *TICKS):
            for pose in self.frames(slot)[:-1]:
                pts = self.points(pose)
                for leg, (hip, knee, heel, toe) in LEGS.items():
                    d = pts[toe] - pts[heel]
                    yaw = math.degrees(math.atan2(d[0], -d[2]))
                    side = 1 if leg == 'RH' else -1
                    self.assertLess(abs(yaw - 7 * side), 9, (slot, leg))

    def test_the_body_sinks_and_rises_twice_a_cycle_by_a_clear_amount(self):
        least = {2: 19, 3: 16, 4: 19}      # the pelvis' height, peak to peak: bounce, hop and the squash of each landing
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)

    def test_the_tired_walk_rides_lower_and_the_run_leans_most(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3, 7), mean(2, 7))              # y grows downward
        self.assertGreater(mean(3, 3), mean(2, 3))
        self.assertGreater(mean(4, 3), mean(3, 3))

    def test_no_key_is_saturated_or_flat_lined(self):
        """The run before clamped: its keys sat at the int16 limit. Now no value touches it and the curves keep moving."""
        for slot in (0, *TICKS):
            frames = self.frames(slot)
            for b in range(1, BONES):
                for i in range(3, 9):
                    for f in frames:
                        self.assertLess(abs(f[b][i]), 30000, (slot, b, i))
        for slot in TICKS:
            frames = self.frames(slot)
            for b in (1, 8, 14):
                spread = max(f[b][3] for f in frames) - min(f[b][3] for f in frames)
                self.assertGreater(spread, 8, (slot, b))        # the chest, head and hips never go flat

    def test_no_tick_jumps(self):
        """No bone turns more than 90 degrees in a tick (a leg's lift-off is one quick swing: the run's 12 ticks at 36 a
        tick give 70-80 in the ankle, the walks 30-55) and the loose parts never more than 22; the body's own bones move
        smoothly: no more than 4 times their median step."""
        np = self.np
        def mat(f, b):
            return np.array(mmd.rot_matrix(*f[b][3:6]), float)[:3, :3]
        for slot in (0, *TICKS):
            frames = self.frames(slot)
            for b in range(2, BONES):
                steps = []
                for t in range(len(frames) - 1):
                    r = mat(frames[t], b).T @ mat(frames[t + 1], b)
                    steps.append(math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(r) - 1) / 2)))))
                self.assertLess(max(steps), 90, (slot, b))
                if b not in LEG_BONES:
                    self.assertLess(max(steps), 22 if slot else 8, (slot, b))
                if b in (8, 14) and max(steps) > 3:
                    med = sorted(steps)[len(steps) // 2]
                    self.assertLess(max(steps), 4 * max(med, 0.5), (slot, b))

    def test_two_strides_differ_in_the_loose_parts_and_agree_in_the_legs(self):
        """The loop plays two strides: the legs, pelvis and chest are the same in both (the feet are planted by them), the
        head, arms, ears, tank and tail are not; the idle is a long loop whose looks and twitches are spread unevenly."""
        for slot, n in CYCLE.items():
            frames = self.frames(slot)
            for b in (1, 14, *LEG_BONES):
                for t in range(n):
                    for i in (3, 4, 5):
                        self.assertIn((frames[t][b][i] - frames[t + n][b][i]) % 4096, (0, 1, 2, 4094, 4095), (slot, b, t))
            for b in (9, 13, 16, 8):
                differ = max(abs((frames[t][b][i] - frames[t + n][b][i] + 2048) % 4096 - 2048) for t in range(n) for i in (3, 4, 5))
                self.assertGreater(differ * 360 / 4096, 1.0, (slot, b))
        frames = self.frames(0)
        for b in (9, 13, 15, 8):
            moving = [t for t in range(len(frames) - 1) if frames[t][b][3:6] != frames[t + 1][b][3:6]]
            self.assertGreater(len(moving), 20, b)

    def test_the_ears_follow_softly_and_mirror(self):
        """Each ear lags the body by 1-3 ticks, moves by under 14 degrees a tick, and the pair mirror each other."""
        for slot in TICKS:
            frames = self.frames(slot)
            n = len(frames) - 1
            for b in EARS:
                steps = []
                for t in range(n):
                    d = [(frames[t + 1][b][i] - frames[t][b][i] + 2048) % 4096 - 2048 for i in (3, 4, 5)]
                    steps.append(max(abs(x) for x in d) * 360 / 4096)
                self.assertLess(max(steps), 14, (slot, b))
                self.assertGreater(max(steps), 0.5, (slot, b))
            spread = lambda b: max(f[b][3] for f in frames) - min(f[b][3] for f in frames)
            self.assertLess(max(spread(9), spread(13)), 3 * min(spread(9), spread(13)) + 8, slot)     # twin ears, not twins in time

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        norm = self.np.linalg.norm
        for slot in TICKS:
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = self.points(pose)
                for leg, (hip, knee, heel, _) in LEGS.items():
                    upper, lower, dist = norm(pts[knee] - pts[hip]), norm(pts[heel] - pts[knee]), norm(pts[heel] - pts[hip])
                    self.assertLess(dist, upper + lower - 1, (slot, leg, tick))

    def swing(self, slot, bone, axis):
        """Peak to peak, in degrees, of one Euler turn of a bone over a clip."""
        values = [f[bone][axis] for f in self.frames(slot)[:-1]]
        turns = self.np.unwrap(self.np.array(values) * 2 * math.pi / 4096) * 180 / math.pi
        return float(turns.max() - turns.min())

    def test_the_hop_and_the_wobble_have_a_minimum_amplitude(self):
        """The walks and the run bounce and squash on each landing, sway from side to side (the pelvis moves across the
        feet), roll the hips and chest, cock the head and swing the tank: a bit, not a flutter."""
        sway = {2: 20, 3: 16, 4: 12}                          # the pelvis' side to side, peak to peak
        roll = {2: (18, 9, 5.5), 3: (16, 8, 4.5), 4: (18, 9, 3.5)}       # hips, chest and head roll, peak to peak (degrees)
        for slot in TICKS:
            frames = self.frames(slot)[:-1]
            across = [f[1][6] for f in frames]
            self.assertGreaterEqual(max(across) - min(across), sway[slot], slot)
            for bone, least in zip((14, 1, 8), roll[slot]):
                self.assertGreaterEqual(self.swing(slot, bone, 5), least, (slot, bone))
            self.assertGreaterEqual(self.swing(slot, 10, 3), 2.5, slot)
            # and not frantic: the pelvis never moves more than 14 units a tick up or down, the head's roll stays small
            height = [f[1][7] for f in self.frames(slot)]
            self.assertLessEqual(max(abs(b - a) for a, b in zip(height, height[1:])), 14, slot)
            self.assertLessEqual(self.swing(slot, 8, 5), 14, slot)
        # the run is the lightest on its feet: its pelvis is highest while both feet are off the floor
        self.assertGreaterEqual(self.swing(4, 14, 5), self.swing(3, 14, 5))

    # ------------------------------------------------------------ the face
    def tex_moves(self, slot):
        return [(t, e['src'], e['size'], e['dst']) for t, kind, e in animsheet.slot_frames(self.new, BONES, slot)[2] if kind == 'tex']

    def states(self, slot):
        eye = {face.eye_move(k)['src']: k for k in (face.OPEN, face.HALF, face.SHUT)}
        mouth = {face.mouth_move(k)['src']: k for k in (face.REST, face.MSHUT, face.AJAR, face.MOPEN, face.WIDE)}
        eyes, mouths = [], []
        for t, src, size, dst in self.tex_moves(slot):
            if dst == face.eye_move(face.OPEN)['dst']:
                eyes.append((t, eye[src]))
            else:
                self.assertEqual(dst, face.mouth_move(face.REST)['dst'])
                mouths.append((t, mouth[src]))
        return eyes, mouths

    def test_every_clip_blinks_and_moves_its_mouth_and_ends_as_it_began(self):
        for slot in (0, *TICKS, 35, 36):      # 33 is the source game's own battle idle (no face frames)
            eyes, mouths = self.states(slot)
            self.assertEqual((eyes[0], mouths[0]), ((0, face.OPEN), (0, face.REST)), slot)
            self.assertEqual((eyes[-1][1], mouths[-1][1]), (face.OPEN, face.REST), slot)
            self.assertGreater(len(eyes), 1, slot)
            self.assertGreater(len(mouths), 1, slot)
            total = len(self.frames(slot)) - 1
            self.assertTrue(all(0 <= t < total for t, _ in eyes + mouths), slot)
        # a blink lasts 3-5 ticks (open to open) and is half, shut, half
        for slot in (0, *TICKS):
            eyes = self.states(slot)[0]
            blinks = []
            for (t, k), (t2, k2) in zip(eyes, eyes[1:]):
                if k == face.OPEN and k2 == face.HALF:
                    start = t2
                if k2 == face.OPEN and k != face.OPEN and t2 != 0:
                    blinks.append(t2 - start)
            self.assertTrue(blinks and all(3 <= b <= 9 for b in blinks), (slot, blinks))
        idle_blinks = sum(1 for _, k in self.states(0)[0] if k == face.SHUT)
        self.assertIn(idle_blinks, (3, 4, 5))
        for slot in (2, 4):
            self.assertEqual(sum(1 for _, k in self.states(slot)[0] if k == face.SHUT), 1, slot)
        # the mouth: breathing in the idle, a little in the walk, drooping in the tired walk, panting wide in the run
        self.assertIn(face.AJAR, [k for _, k in self.states(0)[1]])
        self.assertIn(face.AJAR, [k for _, k in self.states(2)[1]])
        self.assertNotIn(face.WIDE, [k for _, k in self.states(2)[1]])
        self.assertIn(face.MOPEN, [k for _, k in self.states(3)[1]])
        self.assertEqual(sum(1 for _, k in self.states(4)[1] if k == face.WIDE), 2)

    def test_the_aliases_play_the_same_face(self):
        for alias, slot in ((35, 2), (36, 4)):
            self.assertEqual(self.tex_moves(alias), self.tex_moves(slot))
        # the battle idle is the source game's own clip (docs/reference/motion.md), not the field idle's twin
        self.assertNotEqual(self.new.anims.table[33], self.new.anims.table[0])

    def test_the_face_frames_lie_in_texels_no_prim_samples(self):
        used = set()
        for obj in self.new.tmd.objects:
            for p in obj.prims:
                d = p.decode()
                if d['uv']:
                    xs, ys = [u for u, v in d['uv']], [v for u, v in d['uv']]
                    used.update((x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1))
        boxes = [(at, face.EYE_SIZE) for at in face.EYE_FRAMES] + [(at, face.MOUTH_SIZE) for at in face.MOUTH_FRAMES]
        for at, size in boxes:
            self.assertFalse(any((x, y) in used for x in range(at[0], at[0] + size[0]) for y in range(at[1], at[1] + size[1])), at)
            self.assertTrue(at[0] % 4 == 0 and size[0] % 4 == 0)
        for i, (a, sa) in enumerate(boxes):
            for b, sb in boxes[i + 1:]:
                self.assertTrue(a[0] + sa[0] <= b[0] or b[0] + sb[0] <= a[0] or a[1] + sa[1] <= b[1] or b[1] + sb[1] <= a[1])
        # the painted eye and teeth are where the frames paste them, on texels the face's own quads sample
        self.assertTrue(all((x, y) in used for x, y in ((230, 120), (84, 28))))

    def test_the_texture_changes_only_in_the_frames_and_keeps_the_painted_face(self):
        if self.tim0 is None:
            self.skipTest('needs the texture before this change')
        self.assertEqual(hashlib.sha256(self.tim).hexdigest(), EXPECTED_TIM)
        t1 = mmd.Tim4(self.tim)
        self.assertEqual(self.tim0.pal, t1.pal)
        self.assertEqual(face._grab(t1, face.EYE_FRAMES[face.OPEN], face.EYE_SIZE), face._grab(self.tim0, face.EYE_AT, face.EYE_SIZE))
        self.assertEqual(face._grab(t1, face.MOUTH_FRAMES[face.REST], face.MOUTH_SIZE), face._grab(self.tim0, face.MOUTH_AT, face.MOUTH_SIZE))
        frames = [(at, face.EYE_SIZE) for at in face.EYE_FRAMES] + [(at, face.MOUTH_SIZE) for at in face.MOUTH_FRAMES]
        for i in range(len(self.tim0.idx)):
            x, y = i % 256, i // 256
            if not any(a[0] <= x < a[0] + s[0] and a[1] <= y < a[1] + s[1] for a, s in frames):
                self.assertEqual(self.tim0.idx[i], t1.idx[i], (x, y))

    def test_the_shut_eye_is_skin_and_a_lash_and_the_frames_use_the_face_colours(self):
        if self.tim0 is None:
            self.skipTest('needs the texture before this change')
        t1 = mmd.Tim4(self.tim)
        shut = face._grab(t1, face.EYE_FRAMES[face.SHUT], face.EYE_SIZE)
        lo, hi = face.EYE_X[0] - face.EYE_AT[0], face.EYE_X[1] - face.EYE_AT[0] + 1
        self.assertEqual({v for row in shut for v in row[lo:hi]}, {face.CLEAR, face.LASH, face.LASH_SOFT})
        eye = face._grab(self.tim0, face.EYE_AT, face.EYE_SIZE)
        # outside the painted eye's columns a frame is the block as it was
        for state in (face.HALF, face.SHUT):
            frame = face._grab(t1, face.EYE_FRAMES[state], face.EYE_SIZE)
            for y in range(face.EYE_SIZE[1]):
                for x in range(face.EYE_SIZE[0]):
                    if not face.EYE_X[0] <= face.EYE_AT[0] + x <= face.EYE_X[1]:
                        self.assertEqual(frame[y][x], eye[y][x])
        # the half-shut lid hides the top of the eye and leaves the bottom
        half = face._grab(t1, face.EYE_FRAMES[face.HALF], face.EYE_SIZE)
        self.assertEqual(sum(1 for v in half[2][lo:hi] if v != face.CLEAR), 0)
        self.assertGreater(sum(1 for v in half[-1][lo:hi] if v != face.CLEAR), 8)

    def test_the_studio_measures_no_slide_in_stance(self):
        import animstudio
        for slot in TICKS:
            spec = f'{self._write()}:304:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            Path(self._dir, 'm.TIM').write_bytes(self.tim)
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))


if __name__ == '__main__':
    unittest.main()
