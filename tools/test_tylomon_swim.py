"""Check Tylomon's four swimming clips on the real import: different, flowing, seamless and cheap.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 254`). Before the change it is
`tylomon_swim.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
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
from tools.models.field_animations import tylomon_swim as swim

EXPECTED = '1be1bd4c4e935bf62cd3aab08a2116ff1c5d72212175ae53d1bc191e83ba1a52'
NB = swim.NB
SPEEDS = {2: 15, 3: 14, 4: 35}
TICKS = {0: 60, 2: 36, 3: 48, 4: 18}
SPINE_TAIL = (1, 10, 13, 15, 17, 19)


class TylomonSwim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/254-Tylomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 254')
        cls.rig = json.loads(Path('content/species/254-tylomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(254, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == swim.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 254
            data, cls.report = swim.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the import before nor after this change')
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 254

    def frames(self, slot):
        return animsheet.slot_frames(self.model, NB, slot)

    def angles(self, slot):
        """Local joint angles in degrees, unwrapped along the loop (ticks x bones x 3)."""
        frames = self.frames(slot)[0][:-1]
        a = np.array([[v[3:6] for v in p[1:]] for p in frames], float) * 360 / 4096
        return np.degrees(np.unwrap(np.radians((a + 180) % 360 - 180), axis=0, period=2 * np.pi))

    def test_the_bytes_are_the_recorded_result(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)
        if self.old is not None:
            with self.assertRaises(ValueError):
                swim.build(self.data + b'x', self.rig)

    def test_only_the_field_slots_change(self):
        if self.old is None:
            self.skipTest('needs the model before the change')
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(set(changed_programs(self.old, self.model)), {0, 1, 2, 3, 4})
        self.assertEqual(self.frames(1)[0], self.frames(0)[0])

    def test_each_clip_has_its_own_length_and_the_same_distance_every_tick(self):
        self.assertEqual(len({len(self.frames(s)[0]) for s in TICKS}), 4)
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)[0]
            self.assertEqual(len(frames) - 1, ticks)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(steps, {-SPEEDS.get(slot, 0)}, slot)
            self.assertEqual(frames[-1][0][6:8], frames[0][0][6:8])

    def test_the_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)[0]
            for b in range(1, NB):
                for x, y in zip(frames[0][b], frames[-1][b]):
                    self.assertLessEqual(min((x - y) % 4096, (y - x) % 4096), 1, (slot, b))

    def test_tired_is_not_the_run(self):
        tired, run = self.angles(3), self.angles(4)
        # same number of samples after resampling the shorter loop: compare the poses the clips pass through
        def stats(a):
            return a.mean(0), a.std(0)
        (mt, st), (mr, sr) = stats(tired), stats(run)
        self.assertGreater(float(np.abs(mt - mr).max()), 6.)           # a different posture (degrees, one joint at least)
        self.assertGreater(float(np.abs(st - sr).max()), 1.5)          # and a different amount of motion
        self.assertNotEqual(self.frames(3)[0][1][1:], self.frames(4)[0][1][1:])

    def test_a_wave_runs_down_the_body_in_the_travelling_clips(self):
        for slot in (2, 3, 4):
            frames = self.frames(slot)[0][:-1]
            x = []
            for p in frames:
                q = [list(v) for v in p]
                q[0] = [4096] * 3 + [0] * 6
                m = mmd.bone_matrices(self.model, q)
                x.append([m[b][0][3] for b in SPINE_TAIL])
            x = np.array(x)
            f = np.fft.rfft(x - x.mean(0), axis=0)[1]
            phase = ((np.angle(f) - np.angle(f[0]) + np.pi) % (2 * np.pi) - np.pi) / (2 * np.pi)
            # the head leads and every bone further back follows later: the phase falls steadily to the tail (cycles)
            self.assertLess(float(phase[2]), -.15, slot)
            self.assertGreater(float(np.abs(f[-1]) / (len(x) / 2)), 25, slot)    # a tail beat of at least +-25 units

    def test_no_hold_and_snap_and_no_two_tick_beat(self):
        for slot in TICKS:
            a = self.angles(slot).reshape(TICKS[slot], -1)
            moving = a[:, np.ptp(a, axis=0) > 5.]
            self.assertGreater(moving.shape[1], 8, slot)
            d = np.abs(np.roll(moving, -1, 0) - moving)
            hold = float((d < .1 * d.max(0)).mean())
            peak = float((d.max(0) / (d.mean(0) + 1e-9)).mean())
            self.assertLess(hold, .12, slot)                       # the import held still for a quarter of the loop
            self.assertLess(peak, 2.1, slot)                       # and snapped at 2.5 times the mean speed (a sine: 1.57)
            power = np.abs(np.fft.rfft(moving - moving.mean(0), axis=0)) ** 2
            share = power / power[1:].sum(0)
            n = TICKS[slot]
            self.assertLess(float(share[n // 3:].sum(0).max()), .02, slot)   # nothing at a period of three ticks or less
            dominant = np.argmax(share[1:].sum(1)) + 1
            self.assertLessEqual(dominant, 2, slot)                # the slow cycle leads, not a rapid beat

    def test_the_body_stays_off_the_floor(self):
        ident = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        for slot in TICKS:
            low = max(max(v[1] for tri in animsheet.world_tris(self.model, [ident] + p[1:], self.rig) for v in tri[0])
                      for p in self.frames(slot)[0])
            self.assertLess(low, -20, slot)                        # y points down: the floor is 0

    def test_sounds_and_storage(self):
        for slot, count in ((2, 2), (3, 1), (4, 2)):
            self.assertEqual(len(self.frames(slot)[2]), count, slot)
        storage = motionstorage.require(self.data, NB)
        self.assertLess(storage['resident_bytes'], storage['resident_limit'])
        self.assertLessEqual(storage['resident_limit'], 100352)


if __name__ == '__main__':
    unittest.main()
