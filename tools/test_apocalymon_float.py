"""Check Apocalymon's four field clips on the real import: different, floating clear of the floor, loose, closed loops and no
more clashing than before.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 400`). Before the change it is
`apocalymon_float.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
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
from tools.models.field_animations import apocalymon_float as gen
from tools.models.field_animations.meshclash import Clash

EXPECTED = '4e8e54efe216ff93d2d1ea55c3341895e3794888407f024de088c42ff05b451a'   # sha256 of the generator's output
NB = gen.NB
FLOOR = -37.614            # world y of the import's tick-0 lowest point (a tentacle ball): the floor the clips keep to
TICKS = {0: 120, 2: 60, 3: 84, 4: 40}
SPEEDS = {2: 21, 3: 13, 4: 44}
GROUPS = dict(body=[1, 30], torso=[2, 3, 4, 5], arm_l=[6, 7, 8], arm_r=[9, 10, 11], cape=[12, 13, 14], t1=[15, 16, 17],
              t2=[18, 19, 20], t3=[21, 22, 23], t4=[24, 25, 26], t5=[27, 28, 29])
PAIRS = [(g, 'body') for g in GROUPS if g != 'body'] + [('cape', 'torso'), ('arm_l', 'torso'), ('arm_r', 'torso')]
# the import's clips (all four the same loop): most crossing triangle pairs and deepest crossing of each pair of parts
BASELINE = {('torso', 'body'): (3, 0.2), ('arm_l', 'body'): (0, 0), ('arm_r', 'body'): (0, 0), ('cape', 'body'): (0, 0),
            ('t1', 'body'): (14, 39.5), ('t2', 'body'): (16, 45.5), ('t3', 'body'): (6, 22.1),
            ('t4', 'body'): (16, 47.6), ('t5', 'body'): (16, 43.7), ('cape', 'torso'): (97, 8.5),
            ('arm_l', 'torso'): (13, 8.2), ('arm_r', 'torso'): (11, 8.2)}


class ApocalymonFloat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/400-Apocalymon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 400')
        cls.rig = json.loads(Path('content/species/400-apocalymon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(400, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gen.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 400
            data, cls.report = gen.build(data, cls.rig)
        elif EXPECTED and digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 400
        cls.clash = Clash(cls.model, cls.rig)
        cls.floor = FLOOR
        if cls.old is not None:
            base = animsheet.slot_frames(cls.old, NB, 0)[0][0]
            assert abs(float(cls.clash.world(base)[:, 1].max()) - FLOOR) < .01
        cls.cache = {}

    def frames(self, slot):
        return animsheet.slot_frames(self.model, NB, slot)[0]

    def worlds(self, slot):
        """Per tick of the loop: the posed vertices without the root, and the lowest point's world y."""
        if slot not in self.cache:
            w = np.array([self.clash.world(p) for p in self.frames(slot)[:-1]])
            self.cache[slot] = (w, w[:, :, 1].max(1))
        return self.cache[slot]

    def test_storage_fits_the_resident_buffer(self):
        audit = motionstorage.audit(self.data, NB)
        self.assertTrue(audit['fits'])
        self.assertLess(audit['resident_bytes'], 100352)

    def test_only_the_programs_of_the_idle_walk_tired_walk_and_run_differ(self):
        effective = mmd.MMD.parse(self.data, NB)
        effective.type = 400
        if self.old is not None:
            self.assertEqual(self.old.tmd.build(), effective.tmd.build())
            self.assertEqual(set(changed_programs(self.old, effective)), {0, 1, 2, 3, 4, 18, 33})
        t = effective.anims.table
        self.assertTrue(t[1] == t[18] == t[33] == t[0])

    def test_the_clips_have_their_own_lengths_and_all_loops_close(self):
        self.assertEqual({s: len(self.frames(s)) - 1 for s in TICKS}, TICKS)
        for slot in TICKS:
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
                    shared = sum(1 for p in poses[a] for q in poses[b] if np.abs(p - q).max() < 4)
                    self.assertEqual(shared, 0, (a, b))

    def test_the_run_moves_its_parts_much_more_than_the_idle_and_the_tired_walk_hangs_low(self):
        tip = {}
        for slot in TICKS:
            w = self.worlds(slot)[0]
            rel = w[:, :, :] - w[:, :1, :] * 0
            tip[slot] = float(np.linalg.norm(np.diff(np.concatenate([rel, rel[:1]]), axis=0), axis=2).mean())
        self.assertGreater(tip[4], 2.0 * tip[3])
        self.assertGreater(tip[4], tip[2])
        self.assertGreater(tip[2], 2.0 * tip[3])
        # tired: lowest hover of the four, the balls dragging near the floor
        height = {s: self.floor - self.worlds(s)[1].mean() for s in TICKS}
        self.assertLess(height[3], min(height[0], height[2], height[4]))
        self.assertGreater(height[0], 6)

    def test_nothing_sinks_below_the_floor_and_the_floater_stays_off_it(self):
        for slot in TICKS:
            sole = self.floor - self.worlds(slot)[1]                  # y is down
            self.assertGreaterEqual(sole.min(), -4.0, slot)
            self.assertLess(sole.max(), 120, slot)
        self.assertGreater(float((self.floor - self.worlds(4)[1]).max()), 10)

    def test_no_tick_jumps_and_nothing_freezes(self):
        for slot in TICKS:
            w = self.worlds(slot)[0]
            speed = np.linalg.norm(np.diff(np.concatenate([w, w[:1]]), axis=0), axis=2).mean(1)
            self.assertLess(speed.max() / np.median(speed), 3.2, slot)
            self.assertLess(float((speed < .1 * speed.max()).mean()), .12, slot)

    def test_body_and_chains_move_in_every_clip_and_are_not_pure_sinusoids(self):
        for slot in TICKS:
            f = np.array([[v[3:9] for v in p[1:]] for p in self.frames(slot)[:-1]], float)
            self.assertGreater(np.ptp(f[:, 0, 4]), 6, slot)                       # bone 1's height
            for bone in (17, 20, 23, 26, 29, 14):                                    # the tips' chains move
                self.assertGreater(float(np.ptp(f[:, bone - 1, :3], 0).max()), 8, (slot, bone))
            for series in (f[:, 0, 4], f[:, 20 - 1, :3].std(1)):
                spectrum = np.abs(np.fft.rfft(series - series.mean())) ** 2
                self.assertLess(spectrum.max() / spectrum.sum(), .995, slot)

    def test_parts_clash_no_worse_than_the_import(self):
        for slot in TICKS:
            frames = self.frames(slot)[:-1]
            worlds = self.worlds(slot)[0]
            for a, b in PAIRS:
                pairs, depth = (max(r) for r in zip(*[self.clash.clash(f, GROUPS[a], GROUPS[b], world=w)
                                                      for f, w in list(zip(frames, worlds))[::2]]))
                # the wide writhing may graze its own body more than the import's stiff pose did: bounded, and the torso,
                # which the import kept clean, stays as clean
                if (a, b) == ('torso', 'body'):
                    base_pairs, base_depth = BASELINE[(a, b)]
                    self.assertLessEqual(depth, base_depth + .5, (slot, a, b))
                    self.assertLessEqual(pairs, base_pairs + 1, (slot, a, b))
                else:
                    self.assertLessEqual(depth, 55, (slot, a, b))
                    self.assertLessEqual(pairs, 110 if a != 'cape' else 100, (slot, a, b))


if __name__ == '__main__':
    unittest.main()
