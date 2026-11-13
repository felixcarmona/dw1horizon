"""Check Monmon's walk, tired walk and run (species 352) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 352`; MONMON_MODEL names another path).
Before the change it is `monmon_gait.SOURCE`: the generator is run on it and its result checked; afterwards it is the
result itself. Monmon keeps its mesh and proportions: the clips change (idle, walk, tired walk, run) and so do the spare rows of its texture,
where the blink frames sit (the clips copy them over the painted eye).

Monmon faces -z: chest 1, belly 2 (the legs and the tail hang from it), right leg 3-5, tail 6-8, left leg 9-11, right arm
12-14, head 15, leaf crown 16, left arm 17-19, club 20 (the feet are 5 and 11).
"""
import copy
import hashlib
import json
import itertools
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import monmon_gait as gait
from tools.models.field_animations import monmon_face as face

BONES = 21
EXPECTED = '500a5f5ce4d3c6c38b66385e33d7ec1c2a900f190c1e3fd13ab69e720d1cda60'    # the model after this change (the delta's target)
TICKS = {2: 24, 3: 28, 4: 20}               # each clip is two different ground cycles of 12, 14 and 10 ticks
IDLE_TICKS = 60
SPEED = {2: 16, 3: 11, 4: 36}
TOES = {'RH': 5, 'LH': 11}
G = dict(arm_r=[12, 13, 14], arm_l=[17, 18, 19], leg_r=[3, 4, 5], leg_l=[9, 10, 11], belly=[2], chest=[1], head=[15, 16],
         tail=[6, 7, 8], club=[20])
# the most triangles of one part crossing another (meshclash, every second tick, idle and the three gaits), frozen at what the
# new clips measure. The imported clips summed 398 over these pairs, the new ones 347; the belly and the legs overlap more than
# before (70 / 69 then, 98 / 104 now, as deep as before: the legs fold under a ball belly), and the head, tilting from side
# to side, touches the gloves a few triangles more (6 then, 14 / 12 now).
PENETRATION = {('arm_r', 'leg_r'): 4, ('arm_l', 'leg_l'): 4, ('arm_r', 'head'): 14, ('arm_l', 'head'): 12,
               ('arm_r', 'chest'): 10, ('arm_l', 'chest'): 12, ('arm_l', 'club'): 0, ('leg_r', 'tail'): 3,
               ('leg_l', 'tail'): 9, ('belly', 'leg_r'): 98, ('belly', 'leg_l'): 104, ('belly', 'chest'): 33,
               ('belly', 'tail'): 14, ('chest', 'head'): 25, ('head', 'tail'): 0, ('club', 'tail'): 5}


class MonmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('MONMON_MODEL', 'build/imported-model-edit/edit/352-Monmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 352')
        cls.rig = json.loads(Path('content/species/352-monmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[352] = cls.rig
        mmd.exe().bone_count[352] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.report = None
        if digest == gait.SOURCE:
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.tim = path.with_suffix('.TIM')
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 352
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each toe's world position (x, height over the floor, z with the root's travel)."""
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

    def test_the_build_reports_the_gaits_it_changed(self):
        if self.report is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def eye_states(self, slot):
        """The eye frame in force at each tick of the clip (0 open, 1 half shut, 2 shut) from its texture moves."""
        total = len(self.frames(slot)) - 1
        moves = {t: e for t, kind, e in animsheet.slot_frames(self.new, BONES, slot)[2] if kind == 'tex'}
        state, out = None, []
        for t in range(total):
            if t in moves:
                state = moves[t]
            self.assertEqual((state['size'], state['dst']), ((4, 16), (58, 16)))
            out.append(face.EYE_FRAMES.index(state['src'][0] * 4))
        return out

    def test_the_clips_blink_and_end_open(self):
        for slot in (0, 2, 3, 4):
            states = self.eye_states(slot)
            self.assertEqual(states[0], 0, slot)                  # a clip starts open-eyed (it mends a cut blink)
            self.assertEqual(states[-1], 0, slot)                 # and ends so: the loop closes on an open eye
        self.assertEqual(set(self.eye_states(4)), {0})            # the 1 s run keeps its eyes open
        for slot in (0, 2):                                       # one blink, short: shut for 1 tick, half shut for 2 around it
            states = self.eye_states(slot)
            self.assertEqual(states.count(2), 1, slot)
            self.assertLessEqual(sum(1 for k in states if k), 4, slot)
        tired = self.eye_states(3)
        self.assertGreater(tired.count(2), 2)                     # a slow blink holds shut longer than a quick one
        self.assertGreaterEqual(sum(1 for k in tired if k), 12)   # and the eyes droop half shut for a while

    def test_the_blink_frames_are_in_free_texture_rows_and_use_the_face_palette(self):
        old = mmd.Tim4((Path(os.environ.get('MONMON_MODEL', 'build/imported-model-edit/edit/352-Monmon.MMD')).with_suffix('.TIM')).read_bytes())
        new = mmd.Tim4(gait.texture(old.to_bytes())) if hashlib.sha256(old.to_bytes()).hexdigest() == gait.SOURCE_TIM else old
        W = 256
        block = lambda t, at, size: [t.idx[(at[1] + y) * W + at[0] + x] for y in range(size[1]) for x in range(size[0])]
        open_eye = block(new, face.EYE_AT, face.EYE_SIZE)
        self.assertEqual(block(new, (face.EYE_FRAMES[0], face.FRAME_Y), face.EYE_SIZE), open_eye)       # frame 0 is the painted eye
        for k in (1, 2):
            frame = block(new, (face.EYE_FRAMES[k], face.FRAME_Y), face.EYE_SIZE)
            self.assertNotEqual(frame, open_eye)
            self.assertLessEqual(set(frame), set(open_eye) | {face.SKIN, face.SKIN_SHADE, face.SOFT, face.LASH})   # no new colours
        free = (face.FRAME_Y - 16) * W
        self.assertEqual(bytes(new.idx[:free]), bytes(old.idx[:free]))        # the model's own rows 0-63 are untouched
        self.assertTrue(all(v == face.FILLER for v in new.idx[free:face.FRAME_Y * W]))   # rows 64-79 stay free

    def test_the_idle_tilts_the_head_and_loops(self):
        """A 3 s idle on planted feet: the head tilts from side to side (about 8 degrees each way), looks about and dips, the
        leaf crown, club and tail sway, the clip closes on itself. The eyes are part of the head mesh and texture: no bone
        closes them, so there is no blink."""
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 9):
                d = frames[0][b][i] - frames[-1][b][i]
                self.assertLessEqual(abs((d + 2048) % 4096 - 2048) if i < 6 else abs(d), 1, (b, i))
        roll = [((f[15][5] + 2048) % 4096 - 2048) for f in frames]
        self.assertGreater(max(roll) - min(roll), 120)
        for bone in (16, 20, 8):
            sway = max(max(f[bone][k] for f in frames) - min(f[bone][k] for f in frames) for k in (3, 4, 5))
            self.assertGreater(sway, 20, bone)
        for name, bone in TOES.items():
            hs = [self.world(f)[bone] for f in frames]
            xs = [float(self.np.array(m, float)[0, 3]) for m in hs]
            self.assertLess(max(xs) - min(xs), 4, name)

    def test_the_walks_tilt_the_head(self):
        for slot, tilt in ((2, 150), (3, 100), (4, 120)):
            roll = [((f[15][5] + 2048) % 4096 - 2048) for f in self.frames(slot)]
            self.assertGreater(max(roll) - min(roll), tilt, slot)

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
        import animstudio
        for slot in TICKS:
            studio = animstudio.Model(f'{self._write()}:352:{self.tim}', slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 12, (slot, bone))

    def _write(self):
        path = Path(os.environ.get('TMPDIR', '/tmp')) / f'monmon-gait-{os.getpid()}.MMD'
        path.write_bytes(self.data)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_the_feet_do_not_sink_and_lift_clear(self):
        lift = {2: 20, 3: 10, 4: 30}
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                hs = [r[name][1] for r in rows]
                self.assertGreater(min(hs), -12, (slot, name))       # the sole stays on the floor
                self.assertGreater(max(hs) - min(hs), lift[slot], (slot, name))

    def test_the_run_has_a_flight_phase(self):
        rows = self.feet(4)[:-1]
        low = [i for i, r in enumerate(rows) if all(r[n][1] < 12 for n in TOES)]
        air = [i for i, r in enumerate(rows) if all(r[n][1] > 6 for n in TOES)]
        self.assertTrue(air)

    def test_the_gaits_are_not_the_same_clip(self):
        a, b, c = (self.frames(s) for s in (2, 3, 4))
        self.assertNotEqual(a[3][1], b[3][1])
        self.assertNotEqual(a[3][1], c[3][1])

    def test_the_body_moves_against_the_legs(self):
        """The chest bobs, the arms swing against each other, the tail trails, the second cycle is not a copy of the first."""
        for slot, bob in ((2, 5), (3, 3), (4, 8)):
            frames = self.frames(slot)[:-1]
            ys = [f[1][7] for f in frames]
            self.assertGreater(max(ys) - min(ys), bob, slot)
            half = len(frames) // 2
            diff = max(abs(frames[i][b][k] - frames[i + half][b][k]) for i in range(half) for b in range(1, BONES) for k in (3, 4, 5))
            self.assertGreater(diff, 20, slot)       # some joint turns 2 degrees or more differently in the second cycle
            for bone in (12, 17):
                swing = max(max(f[bone][k] for f in frames) - min(f[bone][k] for f in frames) for k in (3, 4, 5))
                self.assertGreater(swing, 40, (slot, bone))      # a swing of 3.5 degrees or more
            tail = [f[7][3] for f in frames]
            self.assertGreater(max(tail) - min(tail), 6, slot)

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

    def test_parts_penetrate_no_more_than_the_recorded_worst(self):
        from tools.models.field_animations import meshclash
        clash = meshclash.Clash(self.new, self.rig)
        worst = {}
        for slot in (0, *TICKS):
            for pose in self.frames(slot)[:-1:2]:
                w = clash.world(pose)
                for a, b in PENETRATION:
                    n, _ = clash.clash(pose, G[a], G[b], world=w)
                    worst[(a, b)] = max(worst.get((a, b), 0), n)
        for pair, most in PENETRATION.items():
            self.assertLessEqual(worst[pair], most, pair)


if __name__ == '__main__':
    unittest.main()
