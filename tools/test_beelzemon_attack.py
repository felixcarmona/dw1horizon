"""Weapon direction, bracing, planted feet, event and 2 MB storage regressions.

Visual review beside native ranged attackers is required independently of these
checks; metrics cannot decide whether an attack reads naturally.
"""
import math
import os
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.repair_beelzemon_attack import repair, SLOTS, PUNCH_SLOTS, CAST_SLOTS


class CannonAttack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('MODEL_REPORT_DIR', 'build/reports')) / 'before/403.MMD'
        if not path.is_file():
            raise unittest.SkipTest('needs the pre-edit provider model in MODEL_REPORT_DIR/before/403.MMD')
        cls.before = mmd.MMD.load(str(path), 403)
        cls.data, cls.proof = repair(cls.before, mmd.exe().skeleton[403])
        cls.after = mmd.MMD.parse(cls.data, 31); cls.after.type = 403

    def test_only_attack_groups_change_and_keep_events(self):
        self.assertEqual(changed_programs(self.before, self.after), list(SLOTS))
        self.assertEqual(self.before.tmd.build(), self.after.tmd.build())
        for group in (PUNCH_SLOTS, CAST_SLOTS):
            self.assertEqual(len({self.after.anims.table[s] for s in group}), 1)
        for slot in SLOTS:
            old, loop, events = animsheet.slot_frames(self.before, 31, slot)
            new, new_loop, new_events = animsheet.slot_frames(self.after, 31, slot)
            self.assertEqual((len(old), loop, events), (len(new), new_loop, new_events))

    def test_cannon_aims_and_free_hand_braces(self):
        for slot, contact in ((46, 6), (50, 18)):
            frames, _, _ = animsheet.slot_frames(self.after, 31, slot)
            worlds = [mmd.bone_matrices(self.after, p) for p in frames]
            self.assertLess(worlds[contact][21][2][1], -.98)
            self.assertLess(worlds[contact][22][2][3], worlds[contact][21][2][3] - 110)
            # The free hand crosses to support the weapon, rather than hanging.
            travel = max(w[18][0][3] for w in worlds) - min(w[18][0][3] for w in worlds)
            self.assertGreater(travel, 100)
            self.assertGreater(worlds[contact][18][1][3], worlds[contact][22][1][3] + 10)

    def test_weight_shift_survives_encoding_without_foot_sliding(self):
        idle, _, _ = animsheet.slot_frames(self.after, 31, 33)
        rest = mmd.bone_matrices(self.after, idle[0])
        for slot in (46, 50):
            frames, _, _ = animsheet.slot_frames(self.after, 31, slot)
            self.assertGreaterEqual(max(p[1][7] for p in frames) - min(p[1][7] for p in frames), 10)
            self.assertGreater(max(p[1][4] for p in frames) - min(p[1][4] for p in frames), 150)
            self.assertGreater(max(p[25][4] for p in frames) - min(p[25][4] for p in frames), 60)
            for pose in frames:
                world = mmd.bone_matrices(self.after, pose)
                for foot in (5, 10):
                    drift = math.sqrt(sum((world[foot][axis][3] - rest[foot][axis][3]) ** 2 for axis in range(3)))
                    self.assertLess(drift, 6, (slot, foot, drift))

    def test_resident_and_cold_reads_fit_original_ram(self):
        after = motionstorage.require(self.data, 31)
        self.assertLessEqual(after['resident_bytes'], 100352)
        self.assertTrue(all(row['fits'] for row in after['cold_reads']))


if __name__ == '__main__':
    unittest.main()
