"""Check Dragomon's four field clips on the real import (`tools/models/edit.py get 291`; skipped when it is absent)."""
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import dragomon_gait as gait

LIMIT = 100352


class DragomonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/291-Dragomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 291')
        cls.rig = json.loads(Path('content/species/291-dragomon.json').read_text())['model']['skeleton']
        cls.data = path.read_bytes()
        cls.model = gait.parse(cls.data, cls.rig)
        cls.m = {s: gait.measure(cls.model, cls.rig, s) for s in gait.SLOTS}

    def test_clips_differ_and_loops_close(self):
        ticks = [self.m[s]['ticks'] - 1 for s in (0, 2, 3, 4)]
        self.assertEqual(len(set(ticks)), 4, ticks)
        for s in gait.SLOTS:
            frames = animsheet.slot_frames(self.model, gait.NB, s)[0]
            a, b = np.array(frames[0], float), np.array(frames[-1], float)
            a[0][8] = b[0][8] = 0
            self.assertLess(np.abs(a - b).max(), 3, s)

    def test_speed_order_and_constant_root_speed(self):
        v = {s: self.m[s]['speed'] for s in (2, 3, 4)}
        self.assertLess(v[3], v[2])
        self.assertLess(v[2], v[4])
        self.assertTrue(10 <= v[3] <= 20 and 35 <= v[4] <= 52, v)
        for s in (2, 3, 4):
            z = [f[0][8] for f in animsheet.slot_frames(self.model, gait.NB, s)[0]]
            self.assertLess(np.ptp(np.diff(z)), 1.01, s)

    def test_planted_soles_do_not_slip(self):
        for s in (2, 3, 4):
            for foot, v in self.m[s]['feet'].items():
                self.assertGreater(v['stance'], 0)
                self.assertLess(v['slip_sole'][0], 25, (s, foot))
                self.assertLess(v['slip_sole'][1], 45, (s, foot))

    def test_floor(self):
        for s in gait.SLOTS:
            self.assertLess(self.m[s]['foot_floor'], 4, s)
            self.assertLess(self.m[s]['arm_floor'], 4, s)

    def test_no_jumps_and_no_penetration(self):
        for s in gait.SLOTS:
            ratio, _ = gait.jumps(self.model, self.rig, s)
            self.assertLess(ratio, 2.0 if s else 2.5, s)
            worst, total = gait.penetration_report(self.model, self.rig, s)
            self.assertEqual(total, 0, (s, worst))

    def test_slow_big_motion_not_flutter(self):
        for s in gait.SLOTS:
            rates = gait.angular_rates(self.model, s)
            for bone, rate in rates.items():
                self.assertLess(rate, 40 if bone in (4, 5, 6, 7) else 20, (s, bone, rate))
            if s:
                share = gait.fast_share(self.model, s, gait.GAIT[s]['cycles'])
                for bone, v in share.items():     # nothing but the feet moves faster than twice the step rate
                    self.assertLess(v, .05, (s, bone, v))

    def test_springs_settle_at_most_once(self):
        n = 48
        for k in range(1, 9):
            sine = [math.cos(2 * math.pi * k * t / n) for t in range(n)]
            for fn in (.75, 1.0, 1.9):
                self.assertLessEqual(max(map(abs, gait.spring(sine, fn * 2, gait.ZETA))), 1.0 + 1e-6, (k, fn))
                # the lag springs (zeta .7) may overshoot a little at the step rate, never ring: no gain above 1.5
                self.assertLessEqual(max(map(abs, gait.spring(sine, fn * 2, gait.ZETA_S))), 1.5, (k, fn))

    def test_buffer(self):
        self.assertLess(motionstorage.audit(self.data, gait.NB)['resident_bytes'], LIMIT)


if __name__ == '__main__':
    unittest.main()
