"""Check Kurisarimon's four field clips on the real import: different, hovering, loose and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 431`). Before the change it is
`kurisarimon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that need the old clips are skipped."""
import copy
import hashlib
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
from tools.models.field_animations import kurisarimon_gait as gen

EXPECTED = '7d9a6e19ca442929fdc950f7188a2d3927250fbef963e580979902b3f1ceb4c9'
NB = gen.NB
TICKS = {0: 72, 2: 32, 3: 48, 4: 20}
SPEEDS = {2: 18, 3: 12, 4: 38}
GROUPS = {leg: chain for leg, (chain, _) in gen.LEGS.items()}
PENETRATION_LIMIT = {0: 5, 2: 17, 3: 17, 4: 17}      # vertices of one limb inside the body or another limb (the import's clips)


class KurisarimonHover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/431-Kurisarimon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 431')
        cls.rig = json.loads(Path('content/species/431-kurisarimon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(431, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 431
            data, cls.report = gen.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 431
        cls.rigger = gen.Hover(cls.model, cls.rig)
        cls.cache = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, NB, slot)[0]

    def test_the_bytes_are_the_recorded_result(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                gen.build(self.data + b'x', self.rig)

    def test_only_the_field_slots_and_those_sharing_the_idle_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), set(gen.SLOTS))
        for slot in gen.TWINS_OF_IDLE:
            self.assertEqual(self.frames(slot), self.frames(0))

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
        self.assertGreater(mean[3], max(mean[0], mean[2], mean[4]) + 10)       # the tired body is the lowest

    def test_the_body_bobs_and_sways_in_every_clip(self):
        bob = {s: np.ptp([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        sway = {s: np.ptp([p[1][6] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertTrue(bob[0] >= 2 and all(b >= 3 for k, b in bob.items() if k), bob)
        self.assertTrue(all(s >= 5 for s in sway.values()), sway)
        self.assertGreater(bob[4], bob[3])          # the run's bob is above the stalking walk's

    def test_idle_body_head_and_tail_move_and_the_legs_sway(self):
        ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(0)[:-1]], float) * 360 / 4096
        rng = ang.max(0) - ang.min(0)
        self.assertGreater(rng[[b - 1 for b in gen.TAIL]].max(), 4)
        self.assertGreater(rng[gen.HEAD - 1].max(), 1.5)
        self.assertGreater(rng[gen.BODY - 1].max(), 1)
        self.assertGreater(rng[[b - 1 for chain, _ in gen.LEGS.values() for b in chain]].max(), 3)

    def test_legs_follow_through_each_bone_a_beat_behind_the_one_above(self):
        for slot in (0, 2, 4):
            ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float)
            n = len(ang)
            lags = []
            for chain, _ in gen.LEGS.values():
                a, b = ang[:, chain[1] - 1, 0] - ang[:, chain[1] - 1, 0].mean(), ang[:, chain[-1] - 1, 0] - ang[:, chain[-1] - 1, 0].mean()
                corr = [np.dot(a, np.roll(b, k)) for k in range(n)]
                lags.append(int(np.argmax(corr)))
            self.assertTrue(any(0 < k < n - 1 for k in lags), (slot, lags))

    def test_leg_and_tail_ranges(self):
        floor = {0: 3, 2: 15, 3: 10, 4: 15}
        for slot, least in floor.items():
            ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float) * 360 / 4096
            rng = ang.max(0) - ang.min(0)
            legs = [b - 1 for chain, _ in gen.LEGS.values() for b in chain]
            palps = [b - 1 for b in gen.TAIL]
            self.assertGreater(rng[legs].max(), least, slot)
            self.assertGreater(rng[palps].max(), 3, slot)
            self.assertLess(rng[legs].max(), 330, slot)

    def test_the_body_hovers_clear_of_the_floor(self):
        body = self.rigger.body
        for slot in TICKS:
            for p in self.frames(slot)[:-1][::2]:
                mats, world = body.world(p)
                belly = float(body.points(world, [gen.BODY])[:, 1].max())
                self.assertLess(belly, -(10 if slot == 3 else 25), slot)     # y is down: above the floor line at 0

    def test_no_tick_jumps(self):
        for slot in TICKS:
            frames = self.frames(slot)
            w = [np.array([np.array(m)[:3, 3] for m in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])])
                 for p in frames]
            step = np.array([np.linalg.norm(w[i + 1] - w[i], axis=1).max() for i in range(len(frames) - 1)])
            self.assertLess(step.max() / np.median(step), 2.5, slot)

    def test_hover_height_is_modest_and_ordered(self):
        body = self.rigger.body
        low = {}
        for slot in TICKS:
            low[slot] = min(-float(body.points(body.world(p)[1], list(range(1, 34)))[:, 1].max()) for p in self.frames(slot)[:-1])
            self.assertGreater(low[slot], 3, slot)       # never touching the floor
            self.assertLess(low[slot], 40, slot)         # the lowest point is never far above it
        mean = {s: np.mean([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertGreater(mean[3] , -300)                 # the tired body hangs low
        self.assertLess(mean[4], mean[2])                  # the run rides higher than the walk
        self.assertLess(mean[4], -300)

    def test_the_run_leans_further_than_the_walk(self):
        ang = {s: np.mean([p[1][3] for p in self.frames(s)[:-1]]) for s in (2, 3, 4)}
        self.assertGreater(abs(ang[4]), abs(ang[2]))

    def test_no_vertex_of_the_model_goes_under_the_floor(self):
        body = self.rigger.body
        for slot in TICKS:
            for p in self.frames(slot)[:-1]:
                low = float(body.points(body.world(p)[1], list(range(1, 34)))[:, 1].max())
                self.assertLess(low, 0., slot)

    def test_the_abdomen_tip_hangs_low_when_tired_and_high_when_running(self):
        body = self.rigger.body
        lift = {}
        for slot in (3, 4):
            lift[slot] = min(-float(body.points(body.world(p)[1], [gen.BODY, gen.HEAD, *gen.TAIL])[:, 1].max())
                             for p in self.frames(slot)[:-1])
        self.assertLess(lift[3], 8)
        self.assertGreater(lift[4], 15)

    def test_penetration_is_not_worse_than_the_import(self):
        body = self.rigger.body
        for slot in TICKS:
            worst = 0
            for p in self.frames(slot)[:-1][::2]:
                mats, world = body.world(p)
                for key, chain in GROUPS.items():
                    others = tuple(b for k, c in GROUPS.items() if k != key for b in c)
                    n = body.count(mats, world, chain[1:], (gen.BODY, gen.HEAD) + gen.TAIL + others) + body.count(mats, world, chain[:1], others)
                    worst = max(worst, n)
            self.assertLessEqual(worst, PENETRATION_LIMIT[slot], slot)

    def test_resident_animation_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertLess(audit['resident_bytes'], 100352)
        self.assertTrue(audit['fits'])


if __name__ == '__main__':
    unittest.main()
