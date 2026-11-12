"""Check Arukenimon's four field clips on the real import: different, planted, solid, loose and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 311`). Before the change it is
`arukenimon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that need the old clips are skipped."""
import copy
import hashlib
import math
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
from tools.models.field_animations import arukenimon_gait as gen

EXPECTED = 'cdcb0414abc32eeefe264513a12c38fb1e8f3f502915a980106a21baf9d380d8'
NB = gen.NB
TICKS = {0: 96, 2: 24, 3: 36, 4: 16}
SPEEDS = {2: 24, 3: 13, 4: 44}
ARMS = {'AL': gen.ARM_L, 'AR': gen.ARM_R}
GROUPS = {**{leg: chain for leg, (chain, _) in gen.LEGS.items()}, **ARMS}
BODY = (gen.PELVIS, gen.TORSO, gen.NECK, gen.HEAD, gen.JAW, gen.ABDOMEN)
# vertices of one limb inside the body or another limb: the worst tick of the rest pose, then of the import's clips
PENETRATION_LIMIT = {0: 9, 2: 24, 3: 8, 4: 17}


class ArukenimonSpider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/311-Arukenimon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 311')
        cls.rig = json.loads(Path('content/species/311-arukenimon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(311, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 311
            data, cls.report = gen.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 311
        cls.rigger = gen.Spider(cls.model, cls.rig)
        cls.cache = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, NB, slot)[0]

    def tips(self, slot):
        """World height and ground position (root travel included) of every leg's tip at every tick of the loop."""
        if slot not in self.cache:
            frames = self.frames(slot)
            res = {leg: [] for leg in gen.LEGS}
            for p in frames:
                q = copy.deepcopy(p)
                for leg in gen.LEGS:
                    w = self.rigger.tip_world(q, leg)
                    res[leg].append((w[1], w[2] + p[0][8]))
            self.cache[slot] = {k: np.array(v) for k, v in res.items()}
        return self.cache[slot]

    def test_the_bytes_are_the_recorded_result(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                gen.build(self.data + b'x', self.rig)

    def test_only_the_field_slots_and_their_twins_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), set(gen.SLOTS))
        for slot, twins in gen.TWINS.items():
            for twin in twins:
                self.assertEqual(self.frames(twin), self.frames(slot))

    def test_each_clip_has_its_own_length_and_a_constant_root_speed(self):
        self.assertEqual(len(set(TICKS.values())), 4)
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(steps, {-SPEEDS.get(slot, 0)}, slot)

    def test_the_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:])

    def test_tired_is_slower_than_walk_and_run_faster_and_the_speeds_are_native(self):
        self.assertTrue(SPEEDS[3] < SPEEDS[2] < SPEEDS[4])
        self.assertTrue(15 <= SPEEDS[2] <= 31 and 10 <= SPEEDS[3] <= 20 and 35 <= SPEEDS[4] <= 52)

    def test_the_four_clips_are_different(self):
        poses = {slot: np.array([[v[3:9] for v in p[1:]] for p in self.frames(slot)[:-1]], float) for slot in TICKS}
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    n = min(len(poses[a]), len(poses[b]))
                    self.assertGreater(np.abs(poses[a][:n] - poses[b][:n]).mean(), 8, (a, b))

    def test_body_heights_order_the_clips(self):
        mean = {s: np.mean([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertGreater(mean[3], max(mean[2], mean[4]) + 10)       # the tired body is lower than the walk and the run
        self.assertGreater(mean[3], mean[0] + 5)                      # and than the idle

    def test_the_body_bobs_and_sways_in_every_clip(self):
        bob = {s: np.ptp([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        sway = {s: np.ptp([p[1][6] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertTrue(bob[0] >= 2 and all(b >= 3 for k, b in bob.items() if k), bob)
        self.assertTrue(all(s >= 5 for k, s in sway.items() if k) and sway[0] >= 3, sway)
        self.assertGreater(bob[4], bob[3])          # the run's bob is above the stalking walk's

    def test_the_torso_moves_a_lot(self):
        """Degrees of yaw, pitch and roll of the torso in the world over a loop (at least twice what the first version had)."""
        floor = {0: (10, 8, 8), 2: (20, 12, 8), 3: (12, 12, 12), 4: (20, 14, 9)}
        for slot, (yw, pt, rl) in floor.items():
            ys, ps, rs = [], [], []
            for p in self.frames(slot)[:-1]:
                r = np.array(mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])[gen.TORSO])[:3, :3]
                r = r / np.linalg.norm(r, axis=0)
                ys.append(math.atan2(r[0, 2], r[2, 2]))
                ps.append(math.asin(max(-1., min(1., -r[1, 2]))))
                rs.append(math.atan2(r[1, 0], r[1, 1]))
            deg = [math.degrees(np.ptp(np.unwrap(a))) for a in (ys, ps, rs)]
            self.assertGreaterEqual(deg[0], yw, (slot, deg))
            self.assertGreaterEqual(deg[1], pt, (slot, deg))
            self.assertGreaterEqual(deg[2], rl, (slot, deg))

    def stance(self, slot, leg):
        """Ticks (of the loop) the tip stands on the floor: it and the next tick are within 2 units of its lowest point."""
        y = self.tips(slot)[leg][:-1, 0]
        low = y > y.max() - 2.0
        return low & np.roll(low, -1)

    def test_stance_tips_do_not_slide(self):
        for slot in (2, 3, 4):
            speed = SPEEDS[slot]
            slips = []
            for leg in gen.LEGS:
                z = self.tips(slot)[leg][:, 1]
                st = self.stance(slot, leg)
                self.assertGreaterEqual(st.sum(), 1, (slot, leg))
                slips += [abs(z[t + 1] - z[t]) / speed * 100 for t in range(len(st)) if st[t]]
            self.assertLess(np.mean(slips), 25, slot)
            self.assertLess(max(slips), 45, slot)

    def test_every_leg_steps_in_the_gaits_and_opposite_legs_alternate(self):
        for slot in (2, 3, 4):
            stand = {leg: self.stance(slot, leg) for leg in gen.LEGS}
            for leg, s in stand.items():
                self.assertTrue(1 <= s.sum() <= len(s) - 2, (slot, leg))
            if slot == 4:
                for a, b in (('RF', 'LF'), ('RM', 'LM'), ('RR', 'LR')):
                    self.assertLess((stand[a] & stand[b]).sum(), .6 * min(stand[a].sum(), stand[b].sum()) + 1, (slot, a, b))

    def test_idle_planted_legs_stay_and_the_woman_moves(self):
        tips = {k: v[:-1] for k, v in self.tips(0).items()}
        for leg in gen.LEGS:
            if leg in gen.PAWS:          # these paw once in place: they leave the floor and come back to the same point
                self.assertLess(np.abs(tips[leg][0] - tips[leg][-1]).max(), 2.5, leg)
                continue
            self.assertLess(np.ptp(tips[leg][:, 1]), 3.5, leg)
            self.assertLess(np.ptp(tips[leg][:, 0]), 5, leg)
        ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(0)[:-1]], float) * 360 / 4096
        rng = ang.max(0) - ang.min(0)
        self.assertGreater(rng[gen.HEAD - 1].max(), 12)       # she glances about
        self.assertGreater(rng[gen.ARM_R[0] - 1].max(), 6)    # an arm lifts

    def test_leg_ranges(self):
        floor = {2: 25, 3: 15, 4: 40}
        for slot, least in floor.items():
            ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float) * 360 / 4096
            rng = ang.max(0) - ang.min(0)
            legs = [b - 1 for chain, _ in gen.LEGS.values() for b in chain]
            self.assertGreater(rng[legs].max(), least, slot)
            self.assertLess(rng[legs].max(), 200, slot)

    def test_the_arms_and_the_head_move_softly(self):
        for slot in TICKS:
            frames = self.frames(slot)
            ang = np.array([[v[3:6] for v in p[1:]] for p in frames], float) * 360 / 4096
            rng = ang.max(0) - ang.min(0)
            step = np.abs(np.diff(ang, axis=0)).max(2)
            for b in gen.ARM_L + gen.ARM_R + (gen.HEAD, gen.TORSO):
                self.assertLess(step[:, b - 1].max(), 18, (slot, b))
                self.assertLess(rng[b - 1].max(), 70, (slot, b))        # the import's sleeves swept 115 to 120 degrees

    def test_no_bone_stretches_or_scales(self):
        """Only rotations move a bone: every joint keeps its distance to its parent and the scale stays 1 (a bone that
        stretches would stretch the mesh): the pelvis alone slides to bob and sway."""
        parent = [p for _, p in self.rig]
        for slot in TICKS:
            frames = self.frames(slot)
            for p in frames[:-1:2]:
                self.assertEqual({tuple(v[:3]) for v in p[1:]}, {(4096, 4096, 4096)}, slot)
                for b in range(2, NB):
                    self.assertEqual(p[b][6:9], frames[0][b][6:9], (slot, b))
                m = [np.array(x)[:3, 3] for x in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])]
                for b in range(2, NB):
                    rest = [np.array(x)[:3, 3] for x in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + frames[0][1:])]
                    self.assertAlmostEqual(float(np.linalg.norm(m[b] - m[parent[b]])), float(np.linalg.norm(rest[b] - rest[parent[b]])), delta=.5)

    def test_no_saturated_or_clamped_keys(self):
        for slot in TICKS:
            a = np.array([[v[3:9] for v in p[1:]] for p in self.frames(slot)], int)
            self.assertLess(np.abs(a[:, :, :3]).max(), 4096 * 2, slot)      # rotations stay inside two turns
            self.assertLess(np.abs(a).max(), 30000, slot)

    def test_the_body_rides_above_the_legs_not_on_the_floor(self):
        body = self.rigger.body
        for slot in TICKS:
            for p in self.frames(slot)[:-1][::2]:
                mats, world = body.world(p)
                belly = float(body.points(world, [gen.ABDOMEN])[:, 1].max())
                self.assertLess(belly, -(10 if slot == 3 else 25), slot)     # y is down: above the floor line at 0

    def test_no_tick_jumps(self):
        for slot in TICKS:
            frames = self.frames(slot)
            w = [np.array([np.array(m)[:3, 3] for m in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])])
                 for p in frames]
            step = np.array([np.linalg.norm(w[i + 1] - w[i], axis=1).max() for i in range(len(frames) - 1)])
            if slot == 0:     # the idle is nearly still: its glances are slow ramps, judged by an absolute step
                self.assertLess(step.max(), 12, slot)
            else:
                self.assertLess(step.max() / np.median(step), 2.5, slot)

    def test_legs_never_sink_under_the_floor_in_stance(self):
        body = self.rigger.body
        for slot in (2, 3, 4):
            frames = self.frames(slot)[:-1]
            for leg, (chain, _) in gen.LEGS.items():
                st = self.stance(slot, leg)
                for t, p in enumerate(frames):
                    if st[t]:
                        low = float(body.points(body.world(p)[1], list(chain))[:, 1].max())
                        self.assertLess(low, gen.FLOOR + 1, (slot, leg, t))

    def test_penetration_is_not_worse_than_the_rest_pose(self):
        body = self.rigger.body
        for slot in TICKS:
            worst = 0
            for p in self.frames(slot)[:-1][::2]:
                mats, world = body.world(p)
                for key, chain in GROUPS.items():
                    others = tuple(b for k, c in GROUPS.items() if k != key for b in c)
                    n = body.count(mats, world, chain[1:], BODY + others) + body.count(mats, world, chain[:1], others)
                    worst = max(worst, n)
            self.assertLessEqual(worst, PENETRATION_LIMIT[slot], slot)

    def test_resident_animation_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertLess(audit['resident_bytes'], 100352)
        self.assertTrue(audit['fits'])


if __name__ == '__main__':
    unittest.main()
