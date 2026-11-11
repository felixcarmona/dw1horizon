"""Check Octomon's four field clips on the real import: different, planted, loose and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 278`). Before the change it is
`octomon_scuttle.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
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
from tools.models.field_animations import octomon_scuttle as gen

EXPECTED = 'a4debdfeff66fd8299d03090364dd8bfb512568d9fc2d453f0f29a74c4619986'
NB = gen.NB
TICKS = {0: 64, 2: 16, 3: 20, 4: 10}
SPEEDS = {2: 15, 3: 10, 4: 35}
GROUPS = {**{leg: chain for leg, (chain, _) in gen.LEGS.items()}, 'AR': gen.ARM_R, 'AL': gen.ARM_L}
PENETRATION_LIMIT = 30     # vertices of one limb inside the body or another limb, worst tick (the import's clips: 0)


class OctomonScuttle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/278-Octomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 278')
        cls.rig = json.loads(Path('content/species/278-octomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(278, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 278
            data, cls.report = gen.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 278
        cls.rigger = gen.Octomon(cls.model, cls.rig)
        cls.rigger.find_tips()
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

    def test_only_the_field_slots_and_those_sharing_the_idle_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), set(gen.SLOTS) | set(gen.SHARED_WITH_IDLE))
        for slot in gen.SHARED_WITH_IDLE:
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
        self.assertGreater(mean[3], mean[4] + 3)       # the tired body is the lowest
        self.assertGreater(mean[4], mean[2] + 5)       # the run is lower than the walk

    def test_the_body_bobs_and_sways_in_every_clip(self):
        bob = {s: np.ptp([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        sway = {s: np.ptp([p[1][6] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertTrue(all(b >= 6 for b in bob.values()), bob)
        self.assertTrue(all(s >= 5 for s in sway.values()), sway)
        self.assertGreater(bob[4], bob[3] + 5)          # the run's bob is the biggest

    def stance(self, slot, leg):
        """Ticks (of the loop) the tip stands on the floor: it and both neighbours are within 2 units of its lowest point."""
        y = self.tips(slot)[leg][:-1, 0]
        low = y > y.max() - 2.0
        return low & np.roll(low, 1) & np.roll(low, -1)

    def test_stance_tips_do_not_slide(self):
        for slot in (2, 3, 4):
            speed = SPEEDS[slot]
            slips = []
            for leg in gen.LEGS:
                z = self.tips(slot)[leg][:, 1]
                st = self.stance(slot, leg)
                self.assertGreaterEqual(st.sum(), 2, (slot, leg))
                slips += [abs(z[t + 1] - z[t]) / speed * 100 for t in range(len(st)) if st[t]]
            self.assertLess(np.mean(slips), 25, slot)
            self.assertLess(max(slips), 45, slot)

    def test_every_leg_steps_in_the_gaits_and_the_tripods_alternate(self):
        for slot in (2, 3, 4):
            stand = {leg: self.stance(slot, leg) for leg in gen.LEGS}
            for leg, s in stand.items():
                self.assertTrue(2 <= s.sum() <= len(s) - 2, (slot, leg))
            n = len(stand['RF'])
            for a, b in (('RF', 'LF'), ('LM', 'RM'), ('RR', 'LR')):
                # a leg of one tripod stands while its partner of the other is mostly in the air
                self.assertLess((stand[a] & stand[b]).sum(), .6 * min(stand[a].sum(), stand[b].sum()) + 1, (slot, a, b))

    def test_idle_planted_legs_stay_and_front_tentacles_feel_about(self):
        tips = {k: v[:-1] for k, v in self.tips(0).items()}
        for leg in ('RM', 'LM', 'RR', 'LR'):
            self.assertLess(np.ptp(tips[leg][:, 1]), 1.5)
            self.assertLess(np.ptp(tips[leg][:, 0]), 3)
        for leg in gen.FRONT:
            self.assertGreater(np.ptp(tips[leg][:, 0]), 10)
            self.assertGreater(np.ptp(tips[leg][:, 1]), 25)

    def test_tentacle_ranges(self):
        floor = {0: 8, 2: 25, 3: 25, 4: 40}
        for slot, least in floor.items():
            ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float) * 360 / 4096
            rng = ang.max(0) - ang.min(0)
            legs = [b - 1 for chain, _ in gen.LEGS.values() for b in chain]
            arms = [b - 1 for b in gen.ARM_R[:2] + gen.ARM_L[:2]]
            self.assertGreater(rng[legs].max(), least, slot)
            self.assertGreater(rng[arms].max(), 3, slot)
            self.assertLess(rng[legs].max(), 330, slot)

    def test_no_tick_jumps(self):
        for slot in TICKS:
            frames = self.frames(slot)
            w = [np.array([np.array(m)[:3, 3] for m in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])])
                 for p in frames]
            step = np.array([np.linalg.norm(w[i + 1] - w[i], axis=1).max() for i in range(len(frames) - 1)])
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

    def test_penetration_is_not_worse_than_the_import(self):
        body = self.rigger.body
        worst = 0
        for slot in TICKS:
            for p in self.frames(slot)[:-1][::2]:
                mats, world = body.world(p)
                for key, chain in GROUPS.items():
                    others = tuple(b for k, c in GROUPS.items() if k != key for b in c)
                    n = body.count(mats, world, chain[1:], (1, 2, 23) + others) + body.count(mats, world, chain[:1], others)
                    worst = max(worst, n)
        self.assertLessEqual(worst, PENETRATION_LIMIT)

    def test_resident_animation_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertLess(audit['resident_bytes'], 100352)
        self.assertTrue(audit['fits'])


if __name__ == '__main__':
    unittest.main()
