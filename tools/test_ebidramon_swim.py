"""Check Ebidramon's four field clips on the real import: different, hovering, loose, seamless and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 305`). Before the change it is
`ebidramon_swim.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
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
from tools.models.field_animations import ebidramon_swim as gen

EXPECTED = "645dfb1ecc182b1501e2ed5cd87c17664aa70667043ab383d230986bb64834be"
NB = gen.NB
TICKS = {0: 96, 2: 48, 3: 64, 4: 32}
SPEEDS = {2: 22, 3: 14, 4: 40}
# vertices of one part inside another at the worst sampled tick in the import's own clips (its parts overlap at rest)
IMPORT_PENETRATION = dict(tail=64, armR=20, armL=19, head=83, antR=0, antL=0, legR=49, legL=32)


class EbidramonSwim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/305-Ebidramon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 305')
        cls.rig = json.loads(Path('content/species/305-ebidramon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(305, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 305
            data, cls.report = gen.build(data, cls.rig)
        elif EXPECTED and digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 305
        cls.swimmer = gen.Swimmer(cls.model, cls.rig)

    def frames(self, slot):
        return animsheet.slot_frames(self.model, NB, slot)[0]

    def test_the_bytes_are_the_recorded_result(self):
        if EXPECTED:
            self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                gen.build(self.data + b'x', self.rig)

    def test_only_the_field_slots_and_those_sharing_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), set(gen.SLOTS))
        for slot in gen.TWINS_OF_IDLE:
            self.assertEqual(self.frames(slot), self.frames(0))
        for slot in gen.TWINS_OF_RUN:
            self.assertEqual(self.frames(slot), self.frames(4))

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
                    self.assertGreater(np.abs(poses[a][:n] - poses[b][:n]).mean(), 5, (a, b))

    def heights(self, slot):
        """Height of the lowest vertex above the floor at every tick."""
        return np.array([-gen.lowest(self.swimmer, p) for p in self.frames(slot)[:-1]])

    def test_it_hovers_and_never_goes_through_the_floor(self):
        mins = {}
        for slot in TICKS:
            h = self.heights(slot)
            mins[slot] = h.min()
            self.assertGreater(h.min(), 4, slot)
            self.assertLess(h.min(), 45, slot)       # the tail fan skims the floor at its lowest
            self.assertLess(h.max(), 220, slot)
        self.assertLess(mins[3], mins[2] + 1)        # the tired one hangs lowest
        self.assertGreater(mins[4], mins[3])

    def test_the_body_bobs_and_sways_in_every_clip(self):
        bob = {s: np.ptp([p[1][7] for p in self.frames(s)[:-1]]) for s in TICKS}
        sway = {s: np.ptp([p[1][6] for p in self.frames(s)[:-1]]) for s in TICKS}
        self.assertTrue(all(b >= 8 for b in bob.values()), bob)
        self.assertTrue(all(s >= 6 for s in sway.values()), sway)
        self.assertGreater(bob[4], bob[2] + 5)       # the run's bounce is the biggest

    def test_the_idle_has_gestures_and_the_gaits_move_every_part(self):
        for slot, least in {0: 6, 2: 15, 3: 8, 4: 25}.items():
            ang = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float) * 360 / 4096
            rng = ang.max(0) - ang.min(0)
            for key, bones in gen.GROUPS.items():
                self.assertGreater(rng[[b - 1 for b in bones]].max(), least / 3, (slot, key))
            self.assertLess(rng.max(), 330, slot)

    def test_no_tick_jumps(self):
        for slot in TICKS:
            frames = self.frames(slot)
            w = [np.array([np.array(m)[:3, 3] for m in mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + p[1:])])
                 for p in frames]
            step = np.array([np.linalg.norm(w[i + 1] - w[i], axis=1).max() for i in range(len(frames) - 1)])
            self.assertLess(step.max() / np.median(step), 2.5, slot)

    def test_penetration_is_small(self):
        body = self.swimmer.body
        worst = {}
        for slot in TICKS:
            for p in self.frames(slot)[:-1][::8]:
                mats, world = body.world(p)
                for key, chain in gen.GROUPS.items():
                    others = tuple(b for k, c in gen.GROUPS.items() if k != key for b in c)
                    n = body.count(mats, world, chain, gen.CORE + others)
                    worst[(slot, key)] = max(worst.get((slot, key), 0), n)
        for (slot, key), n in worst.items():
            self.assertLessEqual(n, IMPORT_PENETRATION[key] * 1.7 + 10, (slot, key, n))

    def test_resident_animation_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertLess(audit['resident_bytes'], 100352)
        self.assertTrue(audit['fits'])


if __name__ == '__main__':
    unittest.main()
