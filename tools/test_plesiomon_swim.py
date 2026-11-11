"""Check Plesiomon's four swimming clips on the real import: different, flowing, seamless, attached and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 271`). Before the change it is
`plesiomon_swim.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
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
from tools.models.field_animations import okuwamon_limbs as meshes
from tools.models.field_animations import plesiomon_swim as swim

EXPECTED = '3759c6be81e60ede2c668e4f1f62762652c1f86eb7aed7821c6a54fe5396c157'
NB = swim.NB
SPEEDS = {0: 0, 2: 22, 3: 15, 4: 39}
TICKS = {0: 72, 2: 40, 3: 60, 4: 24}
GROUPS = {'body': (1,), 'neck': (14, 15, 16, 17, 18), 'head': (19, 20), 'FR': (6, 7), 'FL': (8, 9), 'RR': (2, 3), 'RL': (4, 5),
          'tail': (10, 11, 12, 13)}
ROOT = {'neck': 14, 'head': 19, 'FR': 6, 'FL': 8, 'RR': 2, 'RL': 4, 'tail': 10, 'body': 1}
# vertices of one piece group inside another's mesh (the group's root joint excluded, 60 units around it) in every pose
# of the import's four clips: the rest pose the old clips repeated; a new pose may not be worse in any pair
BASELINE = {('body', 'neck'): 46, ('body', 'FR'): 1, ('body', 'FL'): 1, ('body', 'RR'): 1, ('body', 'RL'): 1, ('body', 'tail'): 11,
            ('neck', 'head'): 53}
# the nearest distance between a piece near its joint and its parent in the old clips (units)
GAPS = {('body', 'neck'): 3, ('neck', 'head'): 10, ('body', 'FR'): 20, ('body', 'FL'): 19, ('body', 'RR'): 23, ('body', 'RL'): 23,
        ('body', 'tail'): 5}
PAIRS = [(a, b) for a in GROUPS for b in GROUPS if a != b and (a, b) not in
         (('body', 'head'), ('head', 'body'), ('tail', 'head'), ('head', 'tail'), ('neck', 'tail'), ('tail', 'neck'))]


class PlesiomonSwim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/271-Plesiomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 271')
        cls.rig = json.loads(Path('content/species/271-plesiomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(271, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == swim.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 271
            data, cls.report = swim.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 271
        cls.mesh = meshes.Body(cls.model, cls.rig)

    def frames(self, slot):
        return animsheet.slot_frames(self.model, NB, slot)

    def positions(self, slot):
        out = []
        for p in self.frames(slot)[0][:-1]:
            q = [list(v) for v in p]
            q[0] = [4096] * 3 + [0] * 6
            m = mmd.bone_matrices(self.model, q)
            out.append([[m[b][i][3] for i in range(3)] for b in range(NB)])
        return np.array(out, float)

    def angles(self, slot):
        frames = self.frames(slot)[0][:-1]
        a = np.array([[v[3:6] for v in p[1:]] for p in frames], float) * 360 / 4096
        return np.degrees(np.unwrap(np.radians((a + 180) % 360 - 180), axis=0, period=2 * np.pi))

    def test_the_bytes_are_the_recorded_result(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                swim.build(self.data + b'x', self.rig)

    def test_only_the_field_slots_change_and_the_aliases_follow_the_idle(self):
        for slot in (1, 18):
            self.assertEqual(self.frames(slot)[0], self.frames(0)[0], slot)
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), {0, 1, 2, 3, 4, 18})
        # the old idle served slots 0, 1 and 18, nothing else
        table = self.old.anims.table
        self.assertEqual({i for i, a in enumerate(table) if a == table[0]}, {0, 1, 18})

    def test_each_clip_has_its_own_length_and_the_same_distance_every_tick(self):
        self.assertEqual(len({len(self.frames(s)[0]) for s in TICKS}), 4)
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)[0]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertEqual({frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}, {-SPEEDS[slot]}, slot)
            self.assertEqual(frames[-1][0][6:8], frames[0][0][6:8])
        self.assertTrue(SPEEDS[3] < SPEEDS[2] < SPEEDS[4])
        self.assertTrue(10 <= SPEEDS[3] <= 20 and 15 <= SPEEDS[2] <= 31 and 35 <= SPEEDS[4] <= 52)
        self.assertTrue(TICKS[4] < TICKS[2] < TICKS[3] < TICKS[0])
        for slot in TICKS:
            for name in ('kn', 'kt'):
                k = swim.CLIPS[swim.CLIP_OF_SLOT[slot]][name]
                self.assertEqual(TICKS[slot] % k, 0)                 # the wave period tiles the loop exactly

    def test_the_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)[0]
            for b in range(1, NB):
                for x, y in zip(frames[0][b], frames[-1][b]):
                    self.assertLessEqual(min((x - y) % 4096, (y - x) % 4096), 1, (slot, b))

    def test_the_four_clips_are_four_different_movements(self):
        poses = {s: [tuple(map(tuple, p[1:])) for p in self.frames(s)[0]] for s in TICKS}
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    self.assertNotEqual(poses[a], poses[b])
                    ma, mb = self.angles(a), self.angles(b)
                    self.assertGreater(float(np.abs(ma.mean(0) - mb.mean(0)).max()), 3., (a, b))     # another posture
                    self.assertGreater(float(np.abs(ma.std(0) - mb.std(0)).max()), 1., (a, b))      # another amount of motion

    def test_the_neck_and_the_tail_carry_a_wave_that_grows_toward_their_ends(self):
        least = {0: (15, 6, 25), 2: (30, 10, 60), 3: (22, 6, 40), 4: (18, 8, 90)}      # head, neck base joint, tail tip (units, peak to peak)
        for slot in TICKS:
            x = self.positions(slot)
            # sideways travel of the neck joints and of the tail tip, relative to the body
            neck = np.ptp(x[:, (15, 17, 19), 0] - x[:, [1], 0], axis=0)
            tail = float(np.ptp(x[:, 13, 0] - x[:, 1, 0]))
            self.assertGreater(float(neck[2]), least[slot][0], slot)
            self.assertGreater(float(neck[0]), least[slot][1], slot)
            self.assertLess(float(neck[0]), float(neck[2]), slot)
            self.assertGreater(tail, least[slot][2], slot)
            self.assertGreater(float(np.ptp(x[:, 19, 1])), 5, slot)       # the head also rises and falls
            y = x[:, (15, 16, 17, 18, 19), 0] - x[:, [1], 0]
            f = np.fft.rfft(y - y.mean(0), axis=0)[swim.CLIPS[swim.CLIP_OF_SLOT[slot]]['kn']]
            phase = ((np.angle(f) - np.angle(f[2]) + np.pi) % (2 * np.pi) - np.pi) / (2 * np.pi)
            self.assertLess(float(phase[4]), -.04, slot)                   # the head follows the neck's middle: a travelling wave
            self.assertLess(float(phase[3]), float(phase[2]) + .01, slot)
        wide = [np.ptp(self.positions(s)[:, 13, 0]) for s in (0, 2, 3, 4)]
        self.assertGreater(wide[3], wide[1])                               # the run's tail lashes most
        self.assertGreater(wide[1], wide[2])
        self.assertGreater(wide[2], wide[0])

    def test_the_flippers_row_each_clip_in_its_own_way(self):
        tips = {s: self.positions(s) for s in TICKS}
        stroke = {s: [float(np.ptp(tips[s][:, b, 2] - tips[s][:, 1, 2])) for b in (7, 9)] for s in TICKS}     # fore and aft
        lift = {s: [float(np.ptp(tips[s][:, b, 1] - tips[s][:, 1, 1])) for b in (7, 9)] for s in TICKS}
        for s, low in ((0, 35), (2, 70), (3, 25), (4, 90)):
            self.assertGreater(min(stroke[s]), low, s)
        for s, low in ((0, 45), (2, 90), (3, 30), (4, 120)):
            self.assertGreater(min(lift[s]), low, s)
        self.assertGreater(stroke[4][0], stroke[2][0])
        self.assertGreater(stroke[2][0], stroke[3][0])
        # left and right half a stroke apart in the walks, together in the run
        for s, together in ((2, False), (3, False), (4, True)):
            right, left = (tips[s][:, b, 2] - tips[s][:, 1, 2] for b in (7, 9))
            corr = float(np.corrcoef(right, left)[0, 1])
            self.assertTrue(corr > .8 if together else corr < -.5, (s, corr))
        # the hind pair follows the front pair a little later
        for s in TICKS:
            front, hind = (tips[s][:, b, 2] - tips[s][:, 1, 2] for b in (7, 3))
            lag = max(range(len(front)), key=lambda k: float(np.corrcoef(np.roll(front, k), hind)[0, 1]))
            self.assertIn(lag, range(1, len(front) // 4), s)

    def test_the_body_bobs_rolls_and_tilts_differently(self):
        mean_y, roll, pitch = {}, {}, {}
        for s in TICKS:
            frames = self.frames(s)[0][:-1]
            mean_y[s] = float(np.mean([p[1][7] for p in frames]))
            q = []
            for p in frames:
                p = [list(v) for v in p]
                p[0] = [4096] * 3 + [0] * 6
                m = mmd.bone_matrices(self.model, p)
                side = np.array([m[1][i][0] for i in range(3)], float)
                fwd = np.array([m[1][i][2] for i in range(3)], float)
                q.append((np.degrees(np.arcsin(side[1] / np.linalg.norm(side))), np.degrees(np.arcsin(fwd[1] / np.linalg.norm(fwd)))))
            q = np.array(q)
            roll[s], pitch[s] = float(np.ptp(q[:, 0])), float(q[:, 1].mean())
        self.assertGreater(roll[2], 4.)
        self.assertGreater(roll[4], 4.)
        self.assertLess(pitch[4], pitch[2] - 4.)               # the run is pitched forward (nose down)
        self.assertLess(mean_y[3], mean_y[2] + 100)
        low = {s: max(max(v[1] for tri in animsheet.world_tris(self.model, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + p[1:], self.rig)
                          for v in tri[0]) for p in self.frames(s)[0]) for s in TICKS}
        for s in TICKS:
            self.assertLess(low[s], -15, s)                    # y points down: the floor is 0
        self.assertGreater(low[3], low[2])                     # the tired swim rides lower than the walk
        self.assertLess(low[4], low[2])                        # and the run higher

    def test_the_condition_walk_sags_and_the_run_stretches_the_neck(self):
        head = {s: self.positions(s)[:, 19, :].mean(0) - self.positions(s)[:, 1, :].mean(0) for s in TICKS}
        self.assertLess(head[3][1], head[2][1] + 1000)          # (guard against a swapped table)
        self.assertGreater(head[3][1], head[2][1] + 25)         # y down: the tired head hangs lower than the walk's
        self.assertGreater(head[4][1], head[2][1] + 25)         # the run's neck is low too
        self.assertLess(head[4][2], head[2][2] - 15)            # and reaches further forward (z grows backward)

    def test_no_hold_and_snap_and_no_two_tick_beat(self):
        for slot in TICKS:
            a = self.angles(slot).reshape(TICKS[slot], -1)
            moving = a[:, np.ptp(a, axis=0) > 5.]
            self.assertGreater(moving.shape[1], 12, slot)
            d = np.abs(np.roll(moving, -1, 0) - moving)
            self.assertLess(float((d < .1 * d.max(0)).mean()), .12, slot)
            self.assertLess(float((d.max(0) / (d.mean(0) + 1e-9)).mean()), 2.1, slot)
            step = np.abs(np.roll(a, -1, 0) - a).max(1)
            self.assertLess(float(step.max() / np.median(step)), 2.5, slot)            # no tick-to-tick jump
            power = np.abs(np.fft.rfft(moving - moving.mean(0), axis=0)) ** 2
            share = power / power[1:].sum(0)
            self.assertLess(float(share[TICKS[slot] // 3:].sum(0).max()), .02, slot)
            self.assertLessEqual(np.argmax(share[1:].sum(1)) + 1, 4, slot)

    def test_nothing_goes_through_anything_more_than_the_import_did_and_nothing_comes_apart(self):
        for slot in TICKS:
            frames = self.frames(slot)[0][:-1]
            worst = {p: 0 for p in PAIRS}
            gap = {p: 0. for p in GAPS}
            for f in frames[::3]:
                mats, world = self.mesh.world(f)
                for a, b in PAIRS:
                    worst[(a, b)] = max(worst[(a, b)], self.mesh.count(mats, world, GROUPS[a], GROUPS[b], socket=ROOT[a], radius=60.))
                for a, b in GAPS:
                    pa, pb = self.mesh.points(world, GROUPS[a]), self.mesh.points(world, GROUPS[b])
                    joint = np.array(mats[ROOT[b]], float)[:3, 3]
                    near = pb[np.linalg.norm(pb - joint, axis=1) < 90]
                    gap[(a, b)] = max(gap[(a, b)], float(np.sqrt(((near[:, None, :] - pa[None]) ** 2).sum(2)).min()))
            for pair, count in worst.items():
                self.assertLessEqual(count, BASELINE.get(pair, 0), (slot, pair))
            for pair, d in gap.items():
                self.assertLessEqual(d, GAPS[pair] + 4, (slot, pair))

    def test_the_eye_still_blinks_once_a_loop_and_storage_fits(self):
        for slot, n in TICKS.items():
            events = self.frames(slot)[2]
            self.assertEqual(len(events), 5, slot)
            self.assertEqual([e[0] for e in events], [0] + [round(n * 19 / 40) + k for k in (0, 1, 3, 4)], slot)
        storage = motionstorage.require(self.data, NB)
        self.assertLess(storage['resident_bytes'], storage['resident_limit'])
        self.assertLessEqual(storage['resident_limit'], 100352)


if __name__ == '__main__':
    unittest.main()
