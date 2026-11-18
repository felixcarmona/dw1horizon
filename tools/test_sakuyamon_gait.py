"""Check Sakuyamon's legs in the walk, tired walk and run (slots 2, 3, 4) and its hair in those and the idle, on the real import (`tools/models/edit.py get 316`; skipped when it is absent)."""
import hashlib
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import okuwamon_limbs as ok
from tools.models.field_animations import sakuyamon_gait as gait
from tools.models.field_animations import sakuyamon_hair as hair
from tools.models.field_animations import sakuyamon_posture as posture

LIMIT = 100352
# the import's other programs (every slot but 0, 2, 3 and 4 and their aliases), its mesh and its slot table, before this change
OTHER_PROGRAMS = '310d350ee087405e4d5b1063ca73c2c436b45dc5308dddd6d61fc25a3bd7c5b5'
# every channel of the walk and tired walk but the hair's (bones 16-18) and of the run but the hair's and the chest, pelvis and head's
# (bones 1, 2, 14, which the posture step turns): the leg gait's, kept
LEGS_AND_BODY = ('400dbe77af23', '50f335fe05f3')
MESH = 'f221acdd0548'
TABLE = 'fc21050fc2a7'
STEPS = {2: [18, 18, 18, 18, 21, 22, 15, 16, 16, 16, 20, 21, 21, 17, 17, 15],         # the import's root motion per tick, kept
         3: [17, 17, 12, 12, 12, 13, 13, 14, 17, 17, 12, 12, 12, 13, 14, 14],
         4: [30, 31, 26, 26, 51, 52, 32, 32, 32, 31, 26, 26, 49, 50, 35, 35]}


class SakuyamonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/316-Sakuyamon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 316')
        cls.data = path.read_bytes()
        cls.model = gait.parse(cls.data)
        cls.gaps = {s: gait.lane_gaps(cls.model, s) for s in gait.SLOTS}
        cls.rest = gait.lane_gaps(cls.model, 0)[0]

    def test_only_the_three_locomotion_programs_changed(self):
        table = self.model.anims.table
        moved = {table[s] for s in hair.SLOTS}
        rest = b''.join(self.model.anims.anims[table[s]].build() for s in range(len(table))
                        if table[s] not in moved and table[s] is not None)
        self.assertEqual(hashlib.sha256(rest).hexdigest(), OTHER_PROGRAMS)
        self.assertEqual(hashlib.sha256(self.model.tmd.build()).hexdigest()[:12], MESH)
        self.assertEqual(hashlib.sha256(repr(table).encode()).hexdigest()[:12], TABLE)
        self.assertEqual(len({table[s] for s in gait.SLOTS}), 3)

    def test_legs_stay_on_two_lanes(self):
        """Per tick the two legs' meshes never close on each other sideways: feet and toes keep clear of the midline (the import's
        crossed by up to 20 and 33 units), the shins and knees keep apart, the ankles stay a hip apart plus."""
        for s, rows in self.gaps.items():
            for t, r in enumerate(rows):
                tag = (s, t)
                self.assertGreaterEqual(r['foot'], 5, tag)
                self.assertGreaterEqual(r['toe'], -5, tag)
                self.assertGreaterEqual(r['shin'], 3, tag)
                self.assertGreaterEqual(r['thigh'], -4, tag)
                self.assertGreaterEqual(r['knee'], 0.95 * 52, tag)       # the idle's knees are 52 apart
                self.assertLessEqual(r['knee'], 100, tag)
                self.assertTrue(76 <= r['ankle'] <= 96, tag)             # the idle's ankles are 73 apart
                self.assertEqual(r['pen'], 0, tag)                       # the legs never cut into each other (the import: up to 48)

    def test_the_lane_is_steady_and_the_feet_turn_out(self):
        for s in gait.SLOTS:
            worlds = [gait.worlds(self.model, f) for f in animsheet.slot_frames(self.model, gait.NB, s)[0]]
            for hip, knee, foot, toe, side in gait.LEGS:
                x = [w[foot, 0, 3] for w in worlds]
                self.assertLess(np.ptp(x), 1.5, (s, foot))               # planted and swinging alike on one lane
                out = [side * gait.lateral_yaw(w[foot, :3, :3]) for w in worlds]
                self.assertTrue(8 <= min(out) and max(out) <= 24, (s, foot, min(out), max(out)))   # the idle's 30, the import's -26..22

    def test_loops_close_and_speeds_are_the_imports(self):
        v = {}
        for s in gait.SLOTS:
            frames = animsheet.slot_frames(self.model, gait.NB, s)[0]
            self.assertEqual(len(frames), 17)
            a, b = np.array(frames[0], float), np.array(frames[-1], float)
            a[0][8] = b[0][8] = 0
            self.assertLess(np.abs(a - b).max(), 3, s)
            z = [f[0][8] for f in frames]
            self.assertEqual([-d for d in np.diff(z)], STEPS[s], s)      # the import's root motion, untouched
            v[s] = abs(z[-1] - z[0]) / 16
        self.assertLess(v[3], v[2])
        self.assertLess(v[2], v[4])
        self.assertTrue(15 <= v[2] <= 31 and 10 <= v[3] <= 20 and 35 <= v[4] <= 52, v)

    def test_soles_at_the_floor_and_steps_smooth(self):
        body = ok.Body(self.model, mmd.exe().skeleton[gait.SPECIES])
        for s in gait.SLOTS:
            frames = animsheet.slot_frames(self.model, gait.NB, s)[0]
            low = []
            for f in frames:
                mats, world = body.world(f)
                low.append(max(float(body.points(world, [b])[:, 1].max()) for b in (5, 6, 9, 10)))
            self.assertLess(max(low), 1.5, s)                            # nothing under the floor
            self.assertGreater(max(low), -3, s)                          # and a sole on it
            worlds = np.array([gait.worlds(self.model, f) for f in frames])
            for b in (4, 5, 6, 8, 9, 10):
                d = np.linalg.norm(np.diff(worlds[:, b, :3, 3], axis=0), axis=1)
                self.assertLess(d.max() / np.median(d), 3.2, (s, b))     # the import's: up to 3.5
            for b in (3, 4, 7, 8):                                       # no thigh or shin twist flip (a bad bend plane: 90 degrees)
                r = worlds[:, b, :3, :3]
                turn = [math.degrees(math.acos(min(1., max(-1., (np.trace(r[i].T @ r[i + 1]) - 1) / 2)))) for i in range(16)]
                self.assertLess(max(turn), 40, (s, b))                   # the import's: up to 41

    def test_the_later_steps_leave_the_leg_gait_alone(self):
        def digest(slots, skip):
            rows = [[f[b][c] for b in range(gait.NB) if b not in skip for c in range(9)]
                    for s in slots for f in animsheet.slot_frames(self.model, gait.NB, s)[0]]
            return hashlib.sha256(repr(rows).encode()).hexdigest()[:12]
        self.assertEqual(digest((2, 3), hair.HAIR), LEGS_AND_BODY[0])
        self.assertEqual(digest((4,), hair.HAIR + (1, 2, 14)), LEGS_AND_BODY[1])

    def test_the_run_is_upright(self):
        """The import's run leans the chest 39 degrees (bone 1) with the head kept straight: a hump. Now the spine (pelvis to the middle of the
        shoulders) and the pelvis-to-head line stay close to the walk's, the chest keeps at most 15 degrees of forward pitch over the idle's, and
        the pelvis and the head lean with it (the import: spine 14..27 degrees forward, head line 20..34)."""
        idle = animsheet.slot_frames(self.model, gait.NB, 0)[0]
        idle_pitch = sum(f[1][3] for f in idle) / len(idle)
        spine, head = [], []
        for f in animsheet.slot_frames(self.model, gait.NB, 4)[0]:
            w = gait.worlds(self.model, f)
            sh, pel, hd = (w[11, :3, 3] + w[19, :3, 3]) / 2, w[2, :3, 3], w[14, :3, 3]
            spine.append(math.degrees(math.atan2(-(sh - pel)[2], -(sh - pel)[1])))
            head.append(math.degrees(math.atan2(-(hd - pel)[2], -(hd - pel)[1])))
            self.assertLessEqual((f[1][3] - idle_pitch) * 360 / 4096, 15, f)
        self.assertTrue(-9 <= min(spine) and max(spine) <= 6, (min(spine), max(spine)))
        self.assertTrue(-4 <= min(head) and max(head) <= 12, (min(head), max(head)))
        self.assertGreater(np.ptp(spine) + np.ptp(head), 3)             # still weighted: the chest rocks with the steps

    def test_the_hair_stays_out_of_the_body(self):
        """Per tick, the hair's vertices inside the chest and pelvis, the arms, the legs and the staff (the import: up to 203 together
        in the run, 32 in the idle, 22 in the walk, 25 in the tired walk; the legs and the staff in the run included). What is left is
        the cap's corners resting on the shoulders (3 each side in every tick, the import's too) and, in the run, an arm swung back."""
        bound = {0: dict(torso=2, arms=6, legs=0, staff=0, total=8),
                 2: dict(torso=2, arms=6, legs=0, staff=0, total=8),
                 3: dict(torso=2, arms=4, legs=0, staff=0, total=6),
                 4: dict(torso=5, arms=10, legs=0, staff=0, total=12)}
        for s, limits in bound.items():
            for t, row in enumerate(hair.measure(self.model, s)):
                for k in ('torso', 'arms', 'legs', 'staff'):
                    self.assertLessEqual(row[k], limits[k], (s, t, k, row))
                self.assertLessEqual(sum(row.values()), limits['total'], (s, t, row))

    def test_the_hair_is_loose_and_the_loop_closes(self):
        """The hair keeps swinging (the sway's spread stays at least a third of the import's) and no channel jumps more than the import's
        own sway does between ticks; the shift back changes slowly; every clip closes on its first tick."""
        for s in hair.SLOTS:
            frames = animsheet.slot_frames(self.model, gait.NB, s)[0]
            for b in hair.HAIR:
                self.assertEqual(frames[0][b], frames[-1][b], (s, b))
            for b in (16, 17):
                x = [f[b][3] for f in frames]
                self.assertGreater(max(x) - min(x), 100, (s, b))
                self.assertLessEqual(max(abs(x[i + 1] - x[i]) for i in range(len(x) - 1)), 110, (s, b))
            shift = [f[16][6:9] for f in frames]
            self.assertLessEqual(max(max(abs(shift[i + 1][k] - shift[i][k]) for k in range(3)) for i in range(len(shift) - 1)), 10, s)

    def test_buffer(self):
        self.assertLess(motionstorage.audit(self.data, gait.NB)['resident_bytes'], LIMIT)


if __name__ == '__main__':
    unittest.main()
