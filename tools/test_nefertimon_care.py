"""Replay the reviewed Nefertimon care layer on the pinned pre-care model."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations import nefertimon_care as care
from tools.models.field_animations.nefertimon import Rig


class NefertimonCare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('NEFERTIMON_BEFORE',
                      'build/nefer-before/imported-species-models/198-nefertimon-pace.MMD'))
        if not source.exists():
            raise unittest.SkipTest('needs the reviewed pre-care paced model (NEFERTIMON_BEFORE)')
        cls.sk = mmd.exe().skeleton[198]
        data, cls.report = care.build(source.read_bytes(), cls.sk)
        cls.old = mmd.MMD.load(str(source), 198)
        cls.new = mmd.MMD.parse(data, 24)
        cls.new.type = 198

    def test_mesh_other_clips_and_original_sleep_events(self):
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(changed_programs(self.old, self.new), [0, 9, 33])
        before, loop, events = animsheet.slot_frames(self.old, 24, 9)
        after, new_loop, new_events = animsheet.slot_frames(self.new, 24, 9)
        self.assertEqual((len(before), loop, events), (len(after), new_loop, new_events))
        for p, q in zip(before, after):
            for b in range(24):
                for c in range(9):
                    if (b, c) not in care.SLEEP_CHANNELS:
                        self.assertEqual(p[b][c], q[b][c], (b, c))
        self.assertTrue(self.report['storage']['fits'])

    def test_idle_retains_every_pose_and_closes_after_phase_shift(self):
        before, loop, events = animsheet.slot_frames(self.old, 24, 0)
        after, new_loop, new_events = animsheet.slot_frames(self.new, 24, 0)
        self.assertEqual((len(before), loop, events), (len(after), new_loop, new_events))
        period = len(before) - 1
        for t, p in enumerate(after):
            q = before[(t + care.IDLE_PHASE) % period]
            self.assertLessEqual(max(abs(a - b) for bone, other in zip(p, q)
                                     for a, b in zip(bone, other)), 2)

    def test_sleep_paw_stays_low_at_ticks_and_interpolated_frames(self):
        frames, _, _ = animsheet.slot_frames(self.new, 24, 9)
        rig = Rig(self.new, self.sk)
        floors, elbow_rotations = [], set()
        for p, q in zip(frames, frames[1:]):
            elbow_rotations.add(tuple(p[5][3:6]))
            for fraction in (0, 1365, 2730):
                pose = interpolate_pose(p, q, fraction)
                world = rig.world(pose)[6]
                floor = rig.lowest(6, [r[:3] for r in world[:3]], [world[i][3] for i in range(3)])
                floors.append(floor)
        self.assertGreater(len(elbow_rotations), 30)  # follows the breathing chest
        self.assertGreater(min(floors), -5)          # no raised, floating paw
        self.assertLess(max(floors), 1.5)           # no ground penetration


if __name__ == '__main__':
    unittest.main()
