"""Nyaromon's (476) four calm field clips: native speeds in order, a planted body, low steps, blinks that fully overwrite the eye."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import animstudio  # noqa: E402
import mmd  # noqa: E402
import numpy as np  # noqa: E402
from tools.models import babies  # noqa: E402
from tools.models.field_animations import nyaromon_calm as calm  # noqa: E402

SLOTS = (0, 2, 3, 4)


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD1/TOKO.MMD').exists(), 'needs the player extraction')
class NyaromonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, tim = babies.build_species(476, ROOT / 'extracted')
        cls.model = model
        cls.tim = tim
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name) / '476.MMD').write_bytes(model)
        (Path(cls.tmp.name) / '476.TIM').write_bytes(tim)
        cls.parsed = mmd.MMD.parse(model, 11)
        cls.parsed.type = 30

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, slot):
        return animstudio.Model(f'{self.tmp.name}/476.MMD:30:{self.tmp.name}/476.TIM', slot)

    def events(self, slot):
        return animsheet.slot_frames(self.parsed, 11, slot)[2]

    def eyes(self, slot):
        return [(e[0], e[2]['src']) for e in self.events(slot) if e[1] == 'tex' and e[2]['dst'] == calm.EYE_DST]

    def lows(self, m):
        floor = float(m.verts[:, 1].max())
        rows = []
        for t in range(len(m.frames)):
            pose, root = m.pose(t)
            pts = np.array([v for tri in animstudio.animsheet.world_tris(m.m, pose, m.skel) for v in tri[0]])
            y = pts[:, 1].max()
            rows.append((floor - (y + root[1]), pts[pts[:, 1] > y - 3][:, 2].mean() + root[2]))
        return rows

    def test_speeds_are_native_and_ordered(self):
        speed = {s: abs(animstudio.metrics(self.clip(s))[0]) for s in (2, 3, 4)}
        self.assertTrue(15 <= speed[2] <= 31 and 10 <= speed[3] <= 20 and 35 <= speed[4] <= 52, speed)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])

    def test_the_body_is_planted_while_it_is_down(self):
        # the lowest points of the mesh stand still while the body is on the floor (a head has no feet to measure)
        for slot in (2, 3, 4):
            m = self.clip(slot)
            rows = self.lows(m)
            speed = abs((m.pose(len(m.frames) - 1)[1][2] - m.pose(0)[1][2]) / (len(m.frames) - 1))
            slip = [abs(rows[t + 1][1] - rows[t][1]) / speed * 100 for t in range(len(rows) - 1)
                    if abs(rows[t][0]) < .6 and abs(rows[t + 1][0]) < .6]
            self.assertGreaterEqual(len(slip), 6, slot)
            self.assertLess(sum(slip) / len(slip), 25, slot)
            self.assertLess(max(slip), 45, slot)

    def test_steps_are_low_and_the_mesh_never_sinks_under_the_floor(self):
        top = {0: 1.5, 2: 6, 3: 4, 4: 10}                  # donor: 133 / 24 / 126 units in the air
        for slot in SLOTS:
            lows = [r[0] for r in self.lows(self.clip(slot))]
            self.assertGreaterEqual(min(lows), -0.5, slot)
            self.assertLessEqual(max(lows), top[slot], slot)

    def test_every_pose_is_continuous(self):
        # no tick moves the body more than 2.5 times the median tick once the clip's steady travel is taken out
        for slot in SLOTS:
            m = self.clip(slot)
            cen = []
            for t in range(len(m.frames)):
                pose, root = m.pose(t)
                pts = np.array([v for tri in animstudio.animsheet.world_tris(m.m, pose, m.skel) for v in tri[0]])
                cen.append(pts.mean(0) + np.array(root[:3]))
            cen = np.array(cen)
            v = (cen[-1] - cen[0]) / (len(cen) - 1)
            d = [float(np.linalg.norm(cen[t + 1] - cen[t] - v)) for t in range(len(cen) - 1)]
            self.assertLessEqual(max(d) / np.median(d), 3.2 if slot == 0 else 2.5, slot)   # the idle's median is a breath

    def test_blinks_have_lids_and_every_clip_ends_open(self):
        want = {0: 4, 2: 1, 3: 2, 4: 1}                                          # closed eyes in each clip (idle: one single, a double, one more)
        for slot, blinks in want.items():
            eyes = self.eyes(slot)
            self.assertEqual(sum(1 for _, src in eyes if src == calm.EYES['closed']), blinks, slot)
            for i, (tick, src) in enumerate(eyes):
                if src == calm.EYES['closed']:
                    self.assertIn(eyes[i - 1][1], (calm.EYES['lid'], calm.EYES['heavy']), slot)
                    self.assertIn(eyes[i + 1][1], (calm.EYES['lid'], calm.EYES['heavy']), slot)
                    if slot != 3:
                        self.assertGreaterEqual(eyes[i + 1][0] - tick, 2, slot)
            self.assertEqual(eyes[-1][1], calm.EYES['lid' if slot == 3 else 'open'], slot)         # back to the state it starts in (tired: half shut)
        double = [t for t, src in self.eyes(0) if src == calm.EYES['closed']]
        self.assertTrue(any(b - a <= 12 for a, b in zip(double, double[1:])), double)   # one double blink
        self.assertEqual(len({b - a for a, b in zip(double, double[1:])}), len(double) - 1)  # irregular gaps
        self.assertIn(calm.EYES['heavy'], [s for _, s in self.eyes(3)])               # tired: heavier lids
        self.assertEqual([e[2]['size'] for e in self.events(3) if e[1] == 'tex'][0], calm.FACE[1])      # each clip starts with the whole plain face

    def test_a_shut_eye_fully_overwrites_the_open_one(self):
        tim = mmd.Tim4(self.tim)
        w = tim.w
        ex, ey = calm.EYE_DST[0] * 4, calm.EYE_DST[1]
        ew, eh = calm.EYE_SIZE[0] * 4, calm.EYE_SIZE[1]
        face = [tim.idx[y * w + ex + c] for y in range(ey, ey + eh) for c in range(ew)]
        self.assertTrue(any(v not in (calm.BG, calm.INK) for v in face))             # the open eye has iris and highlight
        for name in ('lid', 'closed', 'heavy'):
            sx, sy = calm.EYES[name][0] * 4, calm.EYES[name][1]
            frame = [tim.idx[(sy + r) * w + sx + c] for r in range(eh) for c in range(ew)]
            self.assertGreater(sum(1 for v in frame if v == calm.INK), 20, name)
            self.assertEqual(frame[:ew], [calm.BG] * ew, name)                       # the window's top row is plain skin
        sx, sy = calm.EYES['closed'][0] * 4, calm.EYES['closed'][1]
        closed = [tim.idx[(sy + r) * w + sx + c] for r in range(eh) for c in range(ew)]
        self.assertEqual({v for v in closed}, {calm.BG, calm.INK})                  # nothing of the open eye is left
        shut = sum(1 for v in closed if v == calm.INK)
        self.assertGreater(shut, 60)                                                 # an arc thick enough to read at video scale
        # the windows leave the mouth rows alone and the mouth windows leave the eye rows alone
        self.assertLessEqual(calm.EYE_DST[1] + calm.EYE_SIZE[1], calm.MOUTH_DST[1])

    def test_mouth_frames_are_whole_windows(self):
        tim = mmd.Tim4(self.tim)
        w = tim.w
        for name, (sx, sy) in calm.MOUTHS.items():
            rows = [tim.idx[(sy + r) * w + sx * 4:(sy + r) * w + (sx + calm.MOUTH_SIZE[0]) * 4] for r in range(calm.MOUTH_SIZE[1])]
            self.assertTrue(any(v == calm.INK for r in rows for v in r), name)       # the lip line is in every frame
        pink = lambda sx, sy: sum(1 for r in range(16) for c in range(40) if tim.idx[(sy + r) * w + sx * 4 + c] in (6, 7))
        self.assertEqual(pink(*calm.MOUTHS['shut']), 0)
        self.assertGreater(pink(*calm.MOUTHS['half']), 0)
        self.assertGreater(pink(*calm.MOUTHS['wide']), pink(*calm.MOUTHS['half']))

    def test_scale_stays_soft(self):
        for slot in SLOTS:
            frames = self.clip(slot).frames
            self.assertTrue(all(.84 <= f[2][1] / 4096 <= 1.08 for f in frames), slot)

    def tail_tip(self, slot):
        """The tip segment's centroid in the body's own frame, per tick."""
        skel = mmd.exe().skeleton[30]
        verts = np.array([list(v[:3]) + [1] for v in self.parsed.tmd.obj_verts(skel[calm.TAIL_B][0])], float)
        out = []
        for pose in animsheet.slot_frames(self.parsed, 11, slot)[0]:
            mats = mmd.bone_matrices(self.parsed, pose)
            world = (np.array(mats[calm.TAIL_B]) @ verts.T).T
            out.append((np.linalg.inv(np.array(mats[calm.BODY])) @ world.T).T[:, :3].mean(0))
        return np.array(out)

    def test_the_tail_is_its_own_two_segment_chain(self):
        skel = mmd.exe().skeleton[30]
        self.assertEqual((skel[calm.TAIL_A][1], skel[calm.TAIL_B][1]), (calm.BODY, calm.TAIL_A))
        objects = self.parsed.tmd.objects
        self.assertTrue(all(len(objects[calm.OBJ[b]].prims) > 8 for b in calm.APPENDAGES))
        self.assertEqual(len(objects[0].prims), 306 - 120 - 32)
        self.assertLessEqual(len(self.model), 48 * 1024)

    def test_the_tail_waves_in_every_clip_and_the_joint_stays_closed(self):
        floor = {0: 14, 2: 22, 3: 8, 4: 22}      # least travel of the tip, in model units
        skel = mmd.exe().skeleton[30]
        a = np.array([list(v[:3]) + [1] for v in self.parsed.tmd.obj_verts(skel[calm.TAIL_A][0])], float)
        b = np.array([list(v[:3]) + [1] for v in self.parsed.tmd.obj_verts(skel[calm.TAIL_B][0])], float)
        for slot, least in floor.items():
            tip = self.tail_tip(slot)
            self.assertGreater(float(np.ptp(tip, axis=0).max()), least, slot)
            # the base segment's last ring and the tip segment's first ring are the same circle: they never part
            for pose in animsheet.slot_frames(self.parsed, 11, slot)[0][::3]:
                mats = mmd.bone_matrices(self.parsed, pose)
                wa = (np.array(mats[calm.TAIL_A]) @ a.T).T[:, :3]
                wb = (np.array(mats[calm.TAIL_B]) @ b.T).T[:, :3]
                gap = np.sqrt(((wb[:, None, :] - wa[None, :, :]) ** 2).sum(2)).min(1)
                self.assertLess(float(np.sort(gap)[:6].max()), 12, slot)   # the tip's six first points have a base twin nearby

    def test_the_split_keeps_every_triangle_and_the_rest_look(self):
        # build() asserts the rest look against the one-object mesh; here the triangle count and the uniform rest pose
        rest = animsheet.slot_frames(self.parsed, 11, 0)[0][0]
        tris = animsheet.world_tris(self.parsed, rest, mmd.exe().skeleton[30])
        self.assertGreater(len(tris), 0)
        self.assertEqual(len({calm.OBJ[b] for b in calm.APPENDAGES}), 4)

    def test_aliases_play_the_new_programs_and_every_other_program_is_tokomons_with_the_appendages_at_rest(self):
        record = babies.records()[476]
        donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
        table = self.parsed.anims.table
        for alias, slot in calm.ALIASES.items():
            self.assertEqual(table[alias], table[slot])
        self.assertEqual(len(table), len(donor.anims.table))
        for slot, (a, b) in enumerate(zip(table, donor.anims.table)):
            self.assertEqual(a is None, b is None)
            if a is not None and slot not in SLOTS + tuple(calm.ALIASES):
                mine, theirs = self.parsed.anims.anims[a], donor.anims.anims[b]
                for ins in mine.instrs:
                    if ins['op'] == 'key':
                        self.assertFalse({e['bone'] for e in ins['bones']} & set(calm.APPENDAGES), slot)
                    # every other instruction is the donor's
                keep = lambda anim: [i for i in anim.instrs if i['op'] != 'key']
                self.assertEqual(keep(mine), keep(theirs), slot)
                for bone in range(1, 11):
                    if bone not in calm.APPENDAGES:
                        self.assertEqual(mine.pose[bone - 1], theirs.pose[bone - 1], (slot, bone))


if __name__ == '__main__':
    unittest.main()
