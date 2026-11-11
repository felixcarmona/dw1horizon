"""Check Solarmon's whole gears and its four distinct field clips on the real import."""
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import solarmon_gaits as gaits, solarmon_face as face, celebrations

EXPECTED_TIM = '72930f7b5ceb8ef2767063ece379e1a3ed3b1e0b9961d9b7724501be6279dc84'
EXPECTED = '1f271dcfe4ff3997f470add9176fd697df4310287a2fe8cc8c019a36fee1c564'
SLOTS = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


class SolarmonGaits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path('build/imported-model-edit/edit/251-Solarmon.MMD')
        if not source.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 251')
        cls.rig = json.loads(Path('content/species/251-solarmon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(251, cls.rig)
        cls.data, cls.tim, cls.report = gaits.build(source.read_bytes(), cls.rig, source.with_suffix('.TIM').read_bytes())
        cls.tim0 = mmd.Tim4(source.with_suffix('.TIM').read_bytes())
        cls.old = mmd.MMD.parse(celebrations.build(source.read_bytes(), cls.rig)[0], 5)
        cls.new = mmd.MMD.parse(cls.data, 5)
        cls.old.type = cls.new.type = 251

    def frames(self, slot):
        return animsheet.slot_frames(self.new, 5, slot)[0]

    def test_reviewed_output_is_exact(self):
        import hashlib
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        self.assertEqual(hashlib.sha256(self.tim).hexdigest(), EXPECTED_TIM)

    def test_only_the_four_gaits_change_and_the_idle_is_shared(self):
        self.assertEqual(changed_programs(self.old, self.new), [0, 1, 2, 3, 4, 18])
        self.assertEqual(self.new.anims.table[0], self.new.anims.table[18])
        self.assertEqual(self.new.anims.table[0], self.new.anims.table[1])

    def test_storage_fits_the_resident_buffer(self):
        storage = self.report['storage']
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], 100352)

    def test_gears_have_eight_whole_teeth(self):
        # every tooth tip (four corners each) reaches 48 to 55 units from the hub; before, three tips stopped at 34
        for obj in (2, 3):
            reach = [math.hypot(v[0], v[1]) for v in self.new.tmd.obj_verts(obj)]
            self.assertEqual(sum(r >= 47 for r in reach), 32, obj)
        self.assertEqual(self.report['moved_vertices'], 24)

    def test_gear_teeth_are_evenly_spaced_identical_and_mirrored(self):
        tips = {}
        for obj in (2, 3):
            pts = [v for v in self.new.tmd.obj_verts(obj) if math.hypot(v[0], v[1]) >= 33 and v[2] > 0]
            ang = sorted(math.degrees(math.atan2(v[1], v[0])) % 360 for v in pts)
            axes = [(ang[2 * k] + ang[2 * k + 1]) / 2 for k in range(8)]
            gaps = [(axes[(k + 1) % 8] - axes[k]) % 360 for k in range(8)]
            for g in gaps:
                self.assertAlmostEqual(g, 45, delta=0.5)
            radii = [math.hypot(v[0], v[1]) for v in pts]
            self.assertLessEqual(max(radii) - min(radii), 1.5)
            tips[obj] = sorted(round(a) for a in ang)
        self.assertEqual(tips[2], tips[3])

    def test_four_clips_are_different_and_have_the_designed_lengths(self):
        seen = set()
        for slot, clip in SLOTS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, gaits.CLIPS[clip]['n'])
            seen.add(json.dumps(frames))
        self.assertEqual(len(seen), 4)

    def test_root_travels_at_one_speed_every_tick(self):
        for slot, clip in SLOTS.items():
            frames = self.frames(slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)}
            self.assertEqual(steps, {-gaits.CLIPS[clip]['speed']}, clip)

    def test_spins_are_constant_and_whole_steps_per_loop(self):
        for slot, clip in SLOTS.items():
            c = gaits.CLIPS[clip]
            frames = self.frames(slot)
            n = len(frames) - 1
            for bone, step, whole in ((2, gaits.STEP_RING, c['ring']), (3, gaits.STEP_GEAR, c['gear']),
                                      (4, gaits.STEP_GEAR, c['gear'])):
                turned = frames[n][bone][5] - frames[0][bone][5]
                self.assertEqual(abs(turned), step * whole, (clip, bone))
                deltas = [frames[i + 1][bone][5] - frames[i][bone][5] for i in range(n)]
                self.assertLessEqual(max(deltas) - min(deltas), 1, (clip, bone))
                # below the half-symmetry limit: no strobing
                self.assertLess(abs(deltas[0]) * 360 / 4096, 22.5)

    def test_loops_close_without_vertical_jumps(self):
        for slot in SLOTS:
            ys = [f[1][7] for f in self.frames(slot)]
            self.assertEqual(ys[-1], ys[0])
            self.assertLessEqual(max(abs(ys[i + 1] - ys[i]) for i in range(len(ys) - 1)), 3)

    def test_the_hovering_body_clears_the_floor_and_the_gears_stay_off_the_sun(self):
        for slot in SLOTS:
            for frame in self.frames(slot)[:-1]:
                self.assertGreaterEqual(-frame[1][7] - 97 * 1.0 + 0, 0)           # the ring's low point is above 0
                self.assertGreaterEqual(math.hypot(frame[3][6] - 0, frame[3][7] + 0), 90)

    def moves(self, slot):
        a = self.new.anims.anims[self.new.anims.table[slot]]
        return [(i['frame'], (i['src'], i['size'], i['dst'])) for i in a.instrs if i['op'] == 'tex']

    def test_every_clip_starts_and_ends_with_open_eyes(self):
        rest = face.eye_move(face.OPEN)
        rest = (rest['src'], rest['size'], rest['dst'])
        for slot in SLOTS:
            moves = self.moves(slot)
            self.assertIn(rest, [m for f, m in moves if f == 1])
            self.assertEqual(moves[-1][1], rest, f'slot {slot}: the last face change is not open eyes')
            self.assertEqual({m[2] for _, m in moves}, {rest[2]}, 'only the eyes are animated, the mouth stays as painted')

    def test_the_idle_blinks(self):
        eyes = {m[0] for _, m in self.moves(0)}
        self.assertEqual(len(eyes), 3)

    def test_the_frames_lie_in_texels_no_prim_samples(self):
        used = set()
        for obj in self.new.tmd.objects:
            for p in obj.prims:
                d = p.decode()
                if d['uv']:
                    xs, ys = [u for u, v in d['uv']], [v for u, v in d['uv']]
                    used.update((x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1))
        frames = [(at, (24, 8) if at == face.EYE_FRAMES[2] else face.EYE_SIZE) for at in face.EYE_FRAMES]
        for at, size in frames:
            self.assertFalse(any((x, y) in used for x in range(at[0], at[0] + size[0]) for y in range(at[1], at[1] + size[1])), at)

    def test_the_texture_changes_only_in_the_eye_frames(self):
        t0, t1 = self.tim0, mmd.Tim4(self.tim)
        self.assertEqual(face._grab(t1, face.EYE_FRAMES[0], face.EYE_SIZE), face._grab(t0, face.EYE_AT, face.EYE_SIZE))
        self.assertEqual(t0.pal, t1.pal)
        frames = [(at, (24, 8) if at == face.EYE_FRAMES[2] else face.EYE_SIZE) for at in face.EYE_FRAMES]
        for i in range(len(t0.idx)):
            x, y = i % 256, i // 256
            if not any(a[0] <= x < a[0] + s[0] and a[1] <= y < a[1] + s[1] for a, s in frames):
                self.assertEqual(t0.idx[i], t1.idx[i], (x, y))
