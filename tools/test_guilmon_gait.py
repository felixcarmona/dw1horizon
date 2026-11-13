"""Check Guilmon's idle, walk, tired walk and run (species 433) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 433`; GUILMON_MODEL names another
path). Before the change it is `guilmon_gait.SOURCE`: the generator is run on it (about 5 s) and its result checked;
afterwards it is the result itself.

Guilmon faces -z: upper body 1, right arm 2-4, left arm 10-12, neck 5, head 6 with the jaw 7 and the ears 8 and 9, hips 13,
tail 22-24, right leg 14-17 and left leg 18-21 (thigh, shin, ankle, claws).
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
from tools.models.field_animations import guilmon_gait as gait
from tools.models.field_animations import guilmon_face as face
from tools.test_tortomon_gait import inside, DIRS

BONES = 25
EXPECTED = '46e297df38a4f04802688a4286dfe8d1b0b54440356af466e8c1bf498b25eea5'        # the model after this change (the delta's target)
EXPECTED_TIM = '5705362cb359e14b16f7694487cd2135459ff9934755723da8a9b89743636e1e'   # the texture after it
TICKS = {2: 24, 3: 32, 4: 24}               # each clip is two different cycles of 12, 16 and 12 ticks
IDLE_TICKS = 96
SPEED = {2: 15, 3: 10, 4: 36}
TOES = {'LH': 21, 'RH': 17}
LEGS = {'LH': (18, 19, 20, 21), 'RH': (14, 15, 16, 17)}
G = dict(arm_r=[2, 3, 4], arm_l=[10, 11, 12], leg_r=[14, 15, 16, 17], leg_l=[18, 19, 20, 21], hips=[13], torso=[1],
         tail=[22, 23, 24], head=[5, 6, 7, 8, 9])
# vertices and triangle centres inside another part, worst sampled tick, over the idle and the three gaits: for each pair of
# parts the larger of what the imported clips measured and what the new ones do (every second tick).
PENETRATION = {('arm_r', 'arm_l'): 0, ('arm_r', 'leg_r'): 35, ('arm_r', 'leg_l'): 0, ('arm_r', 'hips'): 0, ('arm_r',
               'torso'): 15, ('arm_r', 'tail'): 0, ('arm_r', 'head'): 0, ('arm_l', 'arm_r'): 0, ('arm_l', 'leg_r'): 0, ('arm_l',
               'leg_l'): 26, ('arm_l', 'hips'): 5, ('arm_l', 'torso'): 15, ('arm_l', 'tail'): 0, ('arm_l', 'head'): 1, ('leg_r',
               'arm_r'): 45, ('leg_r', 'arm_l'): 0, ('leg_r', 'leg_l'): 0, ('leg_r', 'hips'): 14, ('leg_r', 'torso'): 0, ('leg_r',
               'tail'): 0, ('leg_r', 'head'): 0, ('leg_l', 'arm_r'): 0, ('leg_l', 'arm_l'): 8, ('leg_l', 'leg_r'): 0, ('leg_l',
               'hips'): 14, ('leg_l', 'torso'): 0, ('leg_l', 'tail'): 6, ('leg_l', 'head'): 0, ('hips', 'arm_r'): 0, ('hips',
               'arm_l'): 0, ('hips', 'leg_r'): 22, ('hips', 'leg_l'): 20, ('hips', 'torso'): 39, ('hips', 'tail'): 36, ('hips',
               'head'): 0, ('torso', 'arm_r'): 14, ('torso', 'arm_l'): 14, ('torso', 'leg_r'): 0, ('torso', 'leg_l'): 0, ('torso',
               'hips'): 7, ('torso', 'tail'): 0, ('torso', 'head'): 13, ('tail', 'arm_r'): 0, ('tail', 'arm_l'): 0, ('tail',
               'leg_r'): 0, ('tail', 'leg_l'): 0, ('tail', 'hips'): 70, ('tail', 'torso'): 0, ('tail', 'head'): 0, ('head', 'arm_r'):
               0, ('head', 'arm_l'): 5, ('head', 'leg_r'): 0, ('head', 'leg_l'): 0, ('head', 'hips'): 11, ('head', 'torso'): 53,
               ('head', 'tail'): 0}


class GuilmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('GUILMON_MODEL', 'build/imported-model-edit/edit/433-Guilmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 433')
        cls.rig = json.loads(Path('content/species/433-guilmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[433] = cls.rig
        mmd.exe().bone_count[433] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.report = None
        if digest == gait.SOURCE:
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        tim = path.with_suffix('.TIM')
        cls.tim0 = cls.tim = None
        if tim.exists():
            raw = tim.read_bytes()
            if hashlib.sha256(raw).hexdigest() == gait.SOURCE_TIM:
                cls.tim0, raw = mmd.Tim4(raw), gait.texture(raw)
            cls.tim = raw
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 433
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._pen = {}

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        np = self.np
        rows = []
        for pose in self.frames(slot):
            mats = self.world(pose)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def inside_count(self, pose, a, b):
        np, mesh = self.np, self.mesh
        world = mesh.world(self.world(pose)).astype(float)
        tri = world[mesh.tri[np.isin(mesh.bone, G[a])]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, G[b])]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_the_build_reports_the_gaits_it_changed(self):
        if self.report is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 33, 35, 36])    # slots 33, 35 and 36 play the idle, the walk and the run as well
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))
        rows = self.feet(0)
        for name in TOES:
            for axis in (0, 2):
                values = [r[name][axis] for r in rows]
                self.assertLess(max(values) - min(values), 4, (name, axis))
            heights = [r[name][1] for r in rows]
            self.assertLess(max(heights) - min(heights), 4, name)

    def test_the_idle_moves_with_character_and_without_jumps(self):
        np, mesh = self.np, self.mesh
        frames = self.frames(0)
        for b, least in ((5, 20), (1, 20), (3, 40), (6, 20)):             # neck, upper body, an upper arm, the head
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)
        speeds, prev = [], None
        for pose in frames:
            world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
            if prev is not None:
                speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
            prev = world
        wide = [sum(speeds[(i + k) % len(speeds)] for k in range(-2, 3)) / 5 for i in range(len(speeds))]
        med = sorted(speeds)[len(speeds) // 2]
        self.assertLess(max(wide), 2.5 * med)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)                # the same step every tick (before: 7 to 10 different steps)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)
        self.assertGreater(TICKS[3], TICKS[2])

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_feet_are_planted_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                hs = [r[name][1] for r in rows]
                stance = [i for i, h in enumerate(hs) if h < min(hs) + 0.25 * (max(hs) - min(hs))]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_studio_measures_no_slide_in_stance(self):
        """The studio's measure: a foot in the lowest quarter of its lift moves over the ground by under 25 % of the
        body's speed on average and 45 % at worst (the chibi clips before: tired walk 172 % mean, 446 % worst)."""
        import animstudio
        for slot in TICKS:
            spec = f'{self._write()}:433:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 12, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            src = Path(os.environ.get('GUILMON_MODEL', 'build/imported-model-edit/edit/433-Guilmon.MMD')).with_suffix('.TIM')
            Path(self._dir, 'm.TIM').write_bytes(src.read_bytes())
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))

    def test_each_foot_strides_and_the_two_stay_on_their_sides(self):
        bounds = {2: 100, 3: 80, 4: 110}          # fore-aft travel of a claw point in the body frame (units)
        for slot in TICKS:
            rows = self.feet(slot)[:-1]
            speed = SPEED[slot]
            for name, side in (('LH', -1), ('RH', 1)):
                self.assertGreater(min(r[name][0] * side for r in rows), 20, (slot, name))
            self.assertGreater(min(abs(r['RH'][0] - r['LH'][0]) for r in rows), 60, slot)
            for name in TOES:
                body = [r[name][2] + speed * i for i, r in enumerate(rows)]
                self.assertGreater(max(body) - min(body), bounds[slot], (slot, name))

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_the_gaits_differ_and_the_tired_walk_rides_lowest(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3, 7), mean(2, 7))              # y grows downward
        self.assertGreater(mean(3, 3), mean(2, 3))
        self.assertGreater(mean(4, 3), mean(3, 3))
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_body_sinks_and_rises_with_every_step_by_a_clear_amount(self):
        least = {2: 14, 3: 12, 4: 20}           # the pelvis' height, peak to peak (the chibi clips: 19 / 31 / 65 in uneven jumps)
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)
            self.assertLessEqual(max(height) - min(height), 40, slot)
            n = len(height)
            smooth = [sum(height[(i + k) % n] for k in (-1, 0, 1)) / 3 for i in range(n)]
            peaks = [i for i in range(n) if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[(i + 1) % n]]
            self.assertEqual(len(peaks), 4, (slot, peaks))       # one dip per step, two steps a cycle

    def test_the_two_cycles_and_the_two_legs_are_not_alike(self):
        """The metronome is broken: the second half of each clip differs from the first (the lifted foot's height, the
        pelvis' dip, the arms), and one leg lifts higher than the other."""
        for slot, ticks in TICKS.items():
            half = ticks // 2
            frames = self.frames(slot)
            for b, least in ((1, 6), (14, 6), (18, 6), (2, 3)):          # pelvis (upper body), the two thighs, an arm
                gap = max(max(abs(frames[i][b][k] - frames[i + half][b][k]) for k in (3, 4, 5)) for i in range(half))
                self.assertGreater(gap, least, (slot, b))
            lifts = {name: max(r[name][1] for r in self.feet(slot)) for name in TOES}
            self.assertGreater(abs(lifts['LH'] - lifts['RH']), 0.5, slot)
            heights = {name: [r[name][1] for r in self.feet(slot)] for name in TOES}
            peaks = {n: [max(h[:half]), max(h[half:])] for n, h in heights.items()}
            self.assertGreater(abs(peaks['LH'][0] - peaks['LH'][1]) + abs(peaks['RH'][0] - peaks['RH'][1]), 0.8, slot)

    def test_the_arms_swing_and_the_tail_trails(self):
        for slot, least in ((2, 20), (3, 10), (4, 18)):
            for b in (4, 12):
                zs = [float(self.np.array(self.world(f)[b], float)[2, 3]) for f in self.frames(slot)[:-1]]
                self.assertGreater(max(zs) - min(zs), least, (slot, b))
            turns = [f[24][4] for f in self.frames(slot)[:-1]]          # the tail tip's yaw
            spread = max(turns) - min(turns)
            self.assertGreater(min(spread, 4096 - spread), 20, slot)

    def test_each_foot_points_along_the_way(self):
        """The toe stays near its own rest direction round the whole loop (the imported clips turned it far off the
        way it points) and the shin never swings more than 45 degrees past vertical."""
        np = self.np
        rest = {}
        pts0 = [np.array(m, float)[:3, 3] for m in self.world(self.frames(0)[0])]
        for leg, (hip, knee, heel, toe) in LEGS.items():
            d = pts0[toe] - pts0[heel]
            rest[leg] = math.degrees(math.atan2(d[0], -d[2]))
        for slot in (0, *TICKS):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = [np.array(m, float)[:3, 3] for m in self.world(pose)]
                for leg, (hip, knee, heel, toe) in LEGS.items():
                    d = pts[toe] - pts[heel]
                    yaw = math.degrees(math.atan2(d[0], -d[2]))
                    side = 1 if leg == 'RH' else -1
                    self.assertLess(abs(yaw - rest[leg]), 25, (slot, leg, tick))
                    shin = pts[heel] - pts[knee]
                    if slot != 4:              # the run kicks the heel high behind the body
                        self.assertLess(math.degrees(math.atan2(shin[2], shin[1])), 135, (slot, leg, tick))

    def test_no_tick_jumps(self):
        np, mesh = self.np, self.mesh
        for slot in TICKS:
            speeds, prev = [], None
            for pose in self.frames(slot):
                world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        np = self.np
        norm = np.linalg.norm
        for slot in TICKS:
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = [np.array(m, float)[:3, 3] for m in self.world(pose)]
                for leg, (hip, knee, heel, _) in LEGS.items():
                    upper, lower, dist = norm(pts[knee] - pts[hip]), norm(pts[heel] - pts[knee]), norm(pts[heel] - pts[hip])
                    self.assertLess(dist, upper + lower - 1, (slot, leg, tick))
                    self.assertGreater(dist, abs(upper - lower) + 5, (slot, leg, tick))

    def test_parts_penetrate_no_more_than_in_the_imported_clips(self):
        for (a, b), most in PENETRATION.items():
            for slot in (0, *TICKS):
                worst = max(self.inside_count(f, a, b) for f in self.frames(slot)[:-1][::2])
                self.assertLessEqual(worst, most, (a, b, slot))

    # ------------------------------------------------------------ the eyes
    def tex_moves(self, slot):
        return [(t, e['src'], e['size'], e['dst']) for t, kind, e in animsheet.slot_frames(self.new, BONES, slot)[2] if kind == 'tex']

    def eyes(self, slot):
        state = {face.eye_move(k)['src']: k for k in (face.OPEN, face.HALF, face.SHUT)}
        out = []
        for t, src, size, dst in self.tex_moves(slot):
            self.assertEqual((size, dst), (face.eye_move(face.OPEN)['size'], face.eye_move(face.OPEN)['dst']))
            out.append((t, state[src]))
        return out

    def test_every_clip_blinks_cleanly_and_ends_as_it_began(self):
        counts = {}
        for slot in (0, *TICKS, 33, 36):
            eyes = self.eyes(slot)
            total = len(self.frames(slot)) - 1
            self.assertEqual(eyes[0], (0, face.OPEN), slot)
            self.assertEqual(eyes[-1][1], face.OPEN, slot)
            self.assertTrue(all(0 <= t < total for t, _ in eyes), slot)
            blinks, start = [], None
            for (t, k), (t2, k2) in zip(eyes, eyes[1:]):
                if k == face.OPEN and k2 == face.HALF:
                    start = t2
                if k2 == face.OPEN and k != face.OPEN:
                    blinks.append((start, t2 - start))
            counts[slot] = len(blinks)
            # half, shut, half, open: the shut eye lasts 2-4 ticks, never a mechanical beat
            for (t, k), (t2, k2) in zip(eyes[1:], eyes[2:]):
                if k == face.SHUT:
                    self.assertTrue(2 <= t2 - t <= 4, (slot, t))
            # a blink lasts 4-9 ticks, the eye never jumps from open to shut
            self.assertTrue(blinks and all(4 <= b <= 9 for _, b in blinks), (slot, blinks))
            self.assertFalse(any({k, k2} == {face.OPEN, face.SHUT} for (_, k), (_, k2) in zip(eyes, eyes[1:])), slot)
        self.assertEqual(counts[0], 3)
        self.assertEqual((counts[2], counts[3], counts[4]), (2, 2, 1))
        gaps = [b - a for (a, _), (b, _) in zip([(t, k) for t, k in self.eyes(0) if k == face.HALF][::2], [(t, k) for t, k in self.eyes(0) if k == face.HALF][2::2])]
        self.assertGreater(len(set(gaps)), 1)                     # irregular intervals
                # tired blinks are heavier: slower than the walk's and the run's
        tired = max(d for _, d in self._blinks(3))
        self.assertGreater(tired, max(d for slot in (0, 2, 4) for _, d in self._blinks(slot)) - 1)

    def _blinks(self, slot):
        eyes, out, start = self.eyes(slot), [], None
        for (t, k), (t2, k2) in zip(eyes, eyes[1:]):
            if k == face.OPEN and k2 == face.HALF:
                start = t2
            if k2 == face.OPEN and k != face.OPEN:
                out.append((start, t2 - start))
        return out

    def test_the_aliases_play_the_same_eyes(self):
        for alias, slot in ((33, 0), (36, 4)):
            self.assertEqual(self.tex_moves(alias), self.tex_moves(slot))

    def test_the_eye_frames_lie_in_texels_no_prim_samples(self):
        used = set()
        for obj in self.new.tmd.objects:
            for p in obj.prims:
                d = p.decode()
                if d['uv']:
                    xs, ys = [u for u, v in d['uv']], [v for u, v in d['uv']]
                    used.update((x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1))
        boxes = [(at, face.EYE_SIZE) for at in face.EYE_FRAMES]
        for at, size in boxes:
            self.assertFalse(any((x, y) in used for x in range(at[0], at[0] + size[0]) for y in range(at[1], at[1] + size[1])), at)
            self.assertTrue(at[0] % 4 == 0 and size[0] % 4 == 0)
        for i, (a, sa) in enumerate(boxes):
            for b, sb in boxes[i + 1:]:
                self.assertTrue(a[0] + sa[0] <= b[0] or b[0] + sb[0] <= a[0] or a[1] + sa[1] <= b[1] or b[1] + sb[1] <= a[1])
        # the painted eye is where the frames paste it, on texels the head's quads sample
        self.assertTrue(all((x, y) in used for x, y in ((95, 25), (100, 26))))

    def test_the_texture_changes_only_in_the_frames_and_keeps_the_painted_eye(self):
        if self.tim0 is None:
            self.skipTest('needs the texture before this change')
        self.assertEqual(hashlib.sha256(self.tim).hexdigest(), EXPECTED_TIM)
        t1 = mmd.Tim4(self.tim)
        self.assertEqual(self.tim0.pal, t1.pal)
        self.assertEqual(face._grab(t1, face.EYE_FRAMES[face.OPEN], face.EYE_SIZE), face._grab(self.tim0, face.EYE_AT, face.EYE_SIZE))
        for i in range(len(self.tim0.idx)):
            x, y = i % 256, i // 256
            if not any(a[0] <= x < a[0] + face.EYE_SIZE[0] and a[1] <= y < a[1] + face.EYE_SIZE[1] for a in face.EYE_FRAMES):
                self.assertEqual(self.tim0.idx[i], t1.idx[i], (x, y))
        # the shut eye has no iris, white or pupil left; the half-shut one keeps the lower part of the iris
        shut = face._grab(t1, face.EYE_FRAMES[face.SHUT], face.EYE_SIZE)
        self.assertFalse(any(v in face.EYE_COLOURS for row in shut for v in row))
        half = face._grab(t1, face.EYE_FRAMES[face.HALF], face.EYE_SIZE)
        self.assertTrue(any(v in face.EYE_COLOURS for row in half[7:] for v in row))
        self.assertFalse(any(v in face.EYE_COLOURS for row in half[:5] for v in row))
        # the frames leave the block's outer ring (the skin and the brow around the eye) as it was
        eye = face._grab(self.tim0, face.EYE_AT, face.EYE_SIZE)
        for frame in (half, shut):
            for y in range(face.EYE_SIZE[1]):
                for x in (0, 1, 2, face.EYE_SIZE[0] - 3, face.EYE_SIZE[0] - 2, face.EYE_SIZE[0] - 1):
                    self.assertEqual(frame[y][x], eye[y][x], (x, y))


if __name__ == '__main__':
    unittest.main()
