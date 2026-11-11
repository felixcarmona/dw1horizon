"""Check Syakomon's four field clips on the real import: different, planted, loose, closed loops and no more clashing than before.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 283`). Before the change it is
`syakomon_hop.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that need the old clips are skipped."""
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
from tools.models.field_animations import syakomon_hop as gen
from tools.models.field_animations.meshclash import Clash

EXPECTED = '3666a13964b02cc562cd1b19c4b145e1a74e1d9b8ccde9462475cc7561e9ad06'
NB = gen.NB
TICKS = {0: 96, 2: 28, 3: 36, 4: 27}
SPEEDS = {2: 16, 3: 11, 4: 38}
HOP = {2: 20, 3: 8, 4: 35}                     # least height (units) a hop's lowest point reaches above the floor
PAIRS = {'shell': ((1,), (6,)), 'fin-lower': ((1,), (2,)), 'fin-upper': ((6,), (2,))}
BASELINE = {'shell': (73, 28.3), 'fin-lower': (41, 17.7), 'fin-upper': (39, 20.6)}   # the import's clips: crossing pairs, depth


class SyakomonHop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/283-Syakomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 283')
        cls.rig = json.loads(Path('content/species/283-syakomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(283, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 283
            data, cls.report = gen.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 283
        cls.clash = Clash(cls.model, cls.rig)
        cls.cache = {}

    def frames(self, slot):
        return animsheet.slot_frames(self.model, NB, slot)[0]

    def worlds(self, slot):
        """Per tick of the loop: the posed vertices without the root, and the lowest point's height."""
        if slot not in self.cache:
            f = self.frames(slot)[:-1]
            w = np.array([self.clash.world(p) for p in f])
            self.cache[slot] = (w, w[:, :, 1].max(1))
        return self.cache[slot]

    def support(self, slot):
        """Where the shell stands along the ground: the mean of its lowest vertices (softly weighted), root travel included."""
        w, low = self.worlds(slot)
        root = np.array([p[0][8] for p in self.frames(slot)[:-1]], float)
        k = np.exp((w[:, :, 1] - low[:, None]) / gen.SUPPORT)
        return (k * w[:, :, 2]).sum(1) / k.sum(1) + root

    def test_storage_fits_the_resident_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertTrue(audit['fits'])
        self.assertLess(audit['resident_bytes'], 100352)

    def test_only_the_five_programs_of_the_idle_walk_and_run_differ(self):
        effective = mmd.MMD.parse(self.data, NB)
        effective.type = 283
        if self.old is not None:
            self.assertEqual(self.old.tmd.build(), effective.tmd.build())
            self.assertEqual(set(changed_programs(self.old, effective)), {0, 1, 2, 3, 4, 18, 33})
        t = effective.anims.table
        self.assertTrue(t[1] == t[18] == t[33] == t[0])

    def test_the_clips_have_their_own_lengths_and_all_loops_close(self):
        self.assertEqual({s: len(self.frames(s)) - 1 for s in TICKS}, TICKS)
        for slot, n in TICKS.items():
            f = self.frames(slot)
            self.assertEqual(f[-1][1:], f[0][1:], slot)
            self.assertEqual(len({len(self.frames(s)) for s in TICKS}), 4)

    def test_the_root_moves_the_same_every_tick_tired_below_walk_below_run(self):
        self.assertTrue(SPEEDS[3] < SPEEDS[2] < SPEEDS[4])
        self.assertTrue(15 <= SPEEDS[2] <= 31 and 10 <= SPEEDS[3] <= 20 and 35 <= SPEEDS[4] <= 52)
        for slot, v in SPEEDS.items():
            z = [p[0][8] for p in self.frames(slot)]
            self.assertEqual(set(np.diff(z)), {-v}, slot)
        self.assertEqual({p[0][8] for p in self.frames(0)}, {0})

    def test_the_four_clips_are_different(self):
        poses = {s: np.array([[v[3:9] for v in p[1:]] for p in self.frames(s)[:-1]], float) for s in TICKS}
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    n = min(len(poses[a]), len(poses[b]))
                    self.assertGreater(np.abs(poses[a][:n] - poses[b][:n]).mean(), 6, (a, b))
        # not one pose in common (the import's four clips were the same 43 poses)
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    shared = sum(1 for p in poses[a] for q in poses[b] if np.abs(p - q).max() < 4)
                    self.assertEqual(shared, 0, (a, b))

    def test_the_lowest_point_never_sinks_and_stands_on_the_floor_in_the_stance(self):
        for slot in TICKS:
            low = self.worlds(slot)[1]
            self.assertLessEqual(low.max(), gen.FLOOR + 2.0, slot)           # y is down: nothing below the floor
            self.assertGreaterEqual(int((low > gen.FLOOR - 1.5).sum()), 3, slot)

    def test_hops_leave_the_floor_clearly(self):
        for slot, least in HOP.items():
            lift = gen.FLOOR - self.worlds(slot)[1].min()
            self.assertGreater(lift, least, slot)
        self.assertGreater(gen.FLOOR - self.worlds(4)[1].min(), gen.FLOOR - self.worlds(2)[1].min() + 10)
        self.assertLess(gen.FLOOR - self.worlds(3)[1].min(), gen.FLOOR - self.worlds(2)[1].min() - 10)

    def test_the_planted_shell_does_not_slide(self):
        for slot, limit in ((2, (15, 30)), (4, (10, 25))):
            low = self.worlds(slot)[1]
            z = self.support(slot)
            stand = low > gen.FLOOR - 1.5
            slip = [abs(z[(t + 1) % len(z)] + (SPEEDS[slot] * len(z) if t + 1 == len(z) else 0) - z[t]) / SPEEDS[slot] * 100
                    for t in range(len(z)) if stand[t] and stand[(t + 1) % len(z)]]
            self.assertGreaterEqual(len(slip), 4, slot)
            self.assertLess(np.mean(slip), limit[0], slot)
            self.assertLess(max(slip), limit[1], slot)
        # the tired shuffle drags on purpose (a quarter of the root's speed in its stance) but is no longer a slide
        low = self.worlds(3)[1]
        z = self.support(3)
        stand = low > gen.FLOOR - 1.5
        slip = [abs(z[t + 1] - z[t]) / SPEEDS[3] * 100 for t in range(len(z) - 1) if stand[t] and stand[t + 1]]
        self.assertLess(np.mean(slip), 60)

    def test_no_tick_jumps_and_nothing_freezes(self):
        for slot in TICKS:
            w = self.worlds(slot)[0]
            speed = np.linalg.norm(np.diff(np.concatenate([w, w[:1]]), axis=0), axis=2).mean(1)
            self.assertLess(speed.max() / np.median(speed), 2.5, slot)
            self.assertGreater(float((speed < .1 * speed.max()).mean()), -1)
            self.assertLess(float((speed < .1 * speed.max()).mean()), .12, slot)

    def test_mouth_fin_and_body_move_in_every_clip_and_are_not_pure_sinusoids(self):
        least = {0: (4, 5, 1.5), 2: (12, 8, 6), 3: (3, 5, 4), 4: (18, 8, 8)}       # mouth degrees, fin degrees, body degrees
        for slot, (mouth, fin, body) in least.items():
            f = np.array([[v[3:6] for v in p[1:]] for p in self.frames(slot)[:-1]], float) / gen.D
            self.assertGreater(np.ptp(f[:, 5, 0]), mouth, slot)                         # bone 6: the upper shell's turn
            self.assertGreater(np.ptp(f[:, 1, 0]) + np.ptp(f[:, 1, 2]), fin, slot)      # bone 2: the fin
            self.assertGreater(np.ptp(f[:, 0, 0]), body, slot)                          # bone 1: the body's pitch
            for series in (f[:, 5, 0], f[:, 1, 0], f[:, 0, 0]):
                spectrum = np.abs(np.fft.rfft(series - series.mean())) ** 2
                self.assertLess(spectrum.max() / spectrum.sum(), .96 if slot else .97, slot)             # more than one harmonic
        gape = -np.array([p[6][3] for p in self.frames(2)[:-1]]) / gen.D
        self.assertGreater(gape.min(), .5)                                              # the shell never shuts through itself

    def test_every_clip_keeps_a_blink(self):
        for slot in TICKS:
            events = animsheet.slot_frames(self.model, NB, slot)[2]
            frames = [e[2]['frame'] for e in events if e[1] == 'tex']
            self.assertGreaterEqual(len(frames), 6, slot)
            self.assertEqual(min(frames), 1)
            self.assertTrue(all(f <= TICKS[slot] for f in frames), slot)

    def test_shell_and_fin_clash_no_worse_than_the_import(self):
        for slot in TICKS:
            frames = self.frames(slot)[:-1]
            for name, (a, b) in PAIRS.items():
                pairs, depth = max(self.clash.clash(f, list(a), list(b)) for f in frames[::2])
                base_pairs, base_depth = BASELINE[name]
                self.assertLessEqual(depth, base_depth + .5, (slot, name))
                self.assertLessEqual(pairs, base_pairs * 1.15, (slot, name))


if __name__ == '__main__':
    unittest.main()
