"""Finisher lift measurement and vertical repairs, without source disc data.

FINISHER_LIFT_ARCHIVE optionally names a real, rebuilt DIGI.DAT to check.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models import finisher_lift as lift


def fixture():
    # Body index 2 deliberately follows its child in the skeleton, like Shurimon.
    idle = np.zeros((3, 3, 9))
    idle[..., :3] = 4096
    idle[:, 2, 7] = -100
    frames = np.repeat(idle[:1], 31, axis=0)
    frames[:, 2, 7] -= 300 * np.sin(np.pi * np.arange(31) / 30) ** 2
    frames[:, 0, 7] = -np.arange(31) * 2
    frames[:, 1, 3] = np.arange(31) * 10  # preserve the arm's acting
    vertices = [(x, y, z) for x in (-20, 20) for y in (0, 100) for z in (-20, 20)]
    return lift.Rig([-1, 2, 0], {2: vertices}, [], {0: (idle, 0), 56: (frames, None)})


class FinisherLift(unittest.TestCase):
    def test_slot_uses_first_finisher_and_ignores_empty_moves(self):
        self.assertEqual(lift.finisher_slot([255, 4, 58, 60]), 48)
        self.assertIsNone(lift.finisher_slot([0, 57, 255]))

    def test_lowest_vertex_uses_idle_height_and_root_travel(self):
        rig = fixture()
        values, height, floor = lift.measure(rig, 56)
        self.assertEqual(height, 100)
        self.assertEqual(floor, 0)
        self.assertAlmostEqual(values[15], 3.3)
        self.assertAlmostEqual(values[-1], .6)

    def test_floor_is_mean_over_idle_but_height_is_first_tick(self):
        rig = fixture()
        idle, _ = rig.frames(0)
        idle[1, 2, 7] += 10
        idle[2, 2, 7] += 20
        values, height, floor = lift.measure(rig, 56)
        self.assertEqual((height, floor), (100, 10))
        self.assertAlmostEqual(values[15], 3.4)

    def test_cap_and_short_hop_keep_timing_and_other_channels(self):
        for hop in (None, [0, 20]):
            with self.subTest(hop=hop):
                rig = fixture()
                before, loop = rig.frames(56)
                saved = before.copy()
                frames, new_loop = lift.cap_lift(rig, 56, .9, hop)
                self.assertEqual(new_loop, loop)
                self.assertEqual(frames.shape, before.shape)
                mask = np.ones(before.shape, bool)
                mask[:, 2, 6:9] = False
                np.testing.assert_array_equal(frames[mask], np.round(before)[mask])
                np.testing.assert_array_equal(before, saved)
                rig._clips[56] = frames, loop
                values = lift.measure(rig, 56)[0]
                self.assertLessEqual(values.max(), .905)
                self.assertGreater(values.max(), .5)
                if hop:
                    self.assertLessEqual(np.abs(values[20:]).max(), .005)

    def test_cli_json_and_exit_status(self):
        for failed in (False, True):
            report = dict(bound_heights=lift.BOUND, passed=not failed,
                          species=[dict(id=225, name='Shurimon', slot=56,
                                        failed=failed, over_bound=failed, peak_heights=1.38 if failed else .9)])
            with tempfile.TemporaryDirectory() as tmp, patch.object(lift, 'check_archive', return_value=report):
                output = Path(tmp) / 'report.json'
                with contextlib.redirect_stdout(io.StringIO()):
                    status = lift.main(['check', 'fixture.DAT', '--json', str(output)])
                self.assertEqual(status, int(failed))
                self.assertEqual(json.loads(output.read_text()), report)

    def archive_fixture(self, rig, native=False):
        record = dict(para=dict(name='Synthetic', moves=[0] * 10 + [58]), bones=[])
        with patch('species.read_archive', return_value=(b'', 1, [record])), \
                patch.object(lift, 'archive_model', return_value=(b'', native)), \
                patch.object(lift.Rig, 'from_mmd', return_value=rig):
            return lift.check_archive('synthetic.DAT')

    def test_real_measurement_controls_archive_gate_and_native_reference(self):
        self.assertFalse(self.archive_fixture(fixture())['passed'])
        native = self.archive_fixture(fixture(), native=True)
        self.assertTrue(native['passed'])
        self.assertTrue(native['species'][0]['over_bound'])
        rig = fixture()
        rig._clips[56] = lift.cap_lift(rig, 56, .9)
        self.assertTrue(self.archive_fixture(rig)['passed'])

    def test_missing_changed_finisher_fails_but_native_npc_is_unavailable(self):
        rig = fixture()
        del rig._clips[56]
        report = self.archive_fixture(rig)
        self.assertFalse(report['passed'])
        self.assertIn('error', report['species'][0])
        native = self.archive_fixture(rig, native=True)
        self.assertTrue(native['passed'])
        self.assertIn('unavailable', native['species'][0])


@unittest.skipUnless(os.environ.get('FINISHER_LIFT_ARCHIVE'), 'FINISHER_LIFT_ARCHIVE names no real archive')
class RealArchive(unittest.TestCase):
    def test_finishers_stay_within_native_bound(self):
        report = lift.check_archive(os.environ['FINISHER_LIFT_ARCHIVE'])
        self.assertTrue(report['species'])
        self.assertTrue(report['passed'], [r for r in report['species'] if r['failed']])


if __name__ == '__main__':
    unittest.main()
