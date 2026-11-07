"""Physical weapon routing and Power Crane preservation on imported models."""
import os
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import animsheet
import mmd
from tools.models.repair_reported_attacks import apocalymon


class ReportedAttacks(unittest.TestCase):
    def load(self, sid):
        path = Path(os.environ.get('FOLLOWUP_REPORT_DIR', 'build/reports/followup')) / f'before/{sid}.MMD'
        if not path.is_file():
            self.skipTest('needs the pre-edit models in FOLLOWUP_REPORT_DIR/before')
        return mmd.MMD.load(str(path), sid)

    def test_power_crane_keeps_core_stable_and_reaches_with_claw(self):
        old = self.load(400); data, report = apocalymon(old)
        new = mmd.MMD.parse(data, 31); new.type = 400
        frames, _, _ = animsheet.slot_frames(new, 31, 51)
        self.assertEqual(report['changed_slots'], [51])
        core_pitch = max(p[1][3] for p in frames) - min(p[1][3] for p in frames)
        claw_swing = max(p[15][3] for p in frames) - min(p[15][3] for p in frames)
        self.assertLess(core_pitch, 100)  # below nine degrees, rather than the shared cast's 71-degree range
        self.assertGreater(claw_swing, 350)
        # Every mechanical chain bends at its own root, elbow and claw.
        for bone in range(15, 30):
            excursion = max(max(p[bone][3 + axis] for p in frames) -
                            min(p[bone][3 + axis] for p in frames) for axis in range(3))
            self.assertGreater(excursion, 200, f'inactive chain segment {bone}')
        for bone in [6, 9]:
            self.assertGreater(max(p[bone][5] for p in frames) - min(p[bone][5] for p in frames), 200)
        ready, _, _ = animsheet.slot_frames(old, 31, 33)
        self.assertEqual(frames[-1], ready[0])

        for slot in [0, 33, 46, 47, 48, 49, 50, *range(52, 61)]:
            self.assertEqual(animsheet.slot_frames(old, 31, slot), animsheet.slot_frames(new, 31, slot))


if __name__ == '__main__':
    unittest.main()
