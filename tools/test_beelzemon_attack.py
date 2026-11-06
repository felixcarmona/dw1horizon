"""Weapon-side, collision-window and 2 MB storage checks for the cannon strike."""
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
            raise unittest.SkipTest('needs the reviewed provider model in MODEL_REPORT_DIR/before/403.MMD')
        cls.before = mmd.MMD.load(str(path), 403)
        cls.skeleton = mmd.exe().skeleton[403]
        cls.data, cls.proof = repair(cls.before, cls.skeleton)
        cls.after = mmd.MMD.parse(cls.data, len(cls.skeleton))
        cls.after.type = 403

    def test_only_shared_hand_strikes_change(self):
        self.assertEqual(changed_programs(self.before, self.after), list(SLOTS))
        self.assertEqual(self.before.tmd.build(), self.after.tmd.build())
        for group in (PUNCH_SLOTS, CAST_SLOTS):
            self.assertEqual(len({self.after.anims.table[s] for s in group}), 1)

    def test_barrel_aims_ahead_through_contact_and_recoil(self):
        for slot in SLOTS:
            frames, loop, events = animsheet.slot_frames(self.after, 31, slot)
            original, old_loop, old_events = animsheet.slot_frames(self.before, 31, slot)
            self.assertEqual((len(frames), loop, events), (len(original), old_loop, old_events))
            for tick in (range(4, 11) if slot in PUNCH_SLOTS else range(10, 33)):
                pose = [b[:] for b in frames[tick]]
                pose[0] = [4096] * 3 + [0] * 6
                world = mmd.bone_matrices(self.after, pose)
                # The mesh's barrel follows forearm-local +Y, on chain 20-23.
                self.assertLess(world[21][2][1], -.97, (slot, tick))
                self.assertLess(world[22][2][3], world[21][2][3] - 110)
                # The bare fist stays below the cannon, rather than punching.
                self.assertGreater(world[18][1][3], world[22][1][3] + 80)

    def test_legs_body_and_events_are_preserved(self):
        changed = {16, 17, 18, 19, 21}
        for slot in SLOTS:
            old, _, _ = animsheet.slot_frames(self.before, 31, slot)
            new, _, _ = animsheet.slot_frames(self.after, 31, slot)
            for a, b in zip(old, new):
                for bone in range(31):
                    if bone not in changed:
                        self.assertEqual(a[bone], b[bone])
                    else:
                        self.assertEqual(a[bone][:3], b[bone][:3])
                        self.assertEqual(a[bone][6:], b[bone][6:])

    def test_resident_and_sector_aligned_cold_reads_fit_original_ram(self):
        before = motionstorage.require(self.before.build(), 31)
        after = motionstorage.require(self.data, 31)
        self.assertLessEqual(after['resident_bytes'], before['resident_bytes'])
        self.assertTrue(all(r['fits'] for r in after['cold_reads']))


if __name__ == '__main__':
    unittest.main()
