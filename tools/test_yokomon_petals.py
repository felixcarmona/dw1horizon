"""Yokomon's (477) tired petals hang open and its neck stays on the bulb; nothing else differs from Tanemon's clips."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import numpy as np  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models import babies  # noqa: E402

NB = 10


def parse(data):
    mmd.exe().skeleton[477] = mmd.exe().skeleton[44]
    mmd.exe().bone_count[477] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = 477
    return model


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD1/TANE.MMD').exists(), 'needs the player extraction')
class YokomonPetals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = babies.build_species(477, ROOT / 'extracted')[0]
        cls.model = parse(cls.data)
        cls.donor = parse((ROOT / 'extracted/CHDAT/MMD1/TANE.MMD').read_bytes())

    def rz(self, model, slot, bone):
        return [f[bone][5] for f in animsheet.slot_frames(model, NB, slot)[0]]

    def test_the_tired_petals_hang_open_like_the_other_clips(self):
        walk = self.rz(self.model, 2, 4)
        idle = self.rz(self.model, 0, 4)
        tired = self.rz(self.model, 3, 4)
        self.assertLess(max(tired), 0, 'bone 4 never rises above its rest angle (the folded bud is rz > 0)')
        self.assertTrue(min(idle) <= min(tired) <= max(tired) <= max(walk), (min(idle), min(tired), max(tired), max(walk)))
        self.assertGreater(max(tired) - min(tired), 60, 'they move with the body')
        self.assertEqual(tired, [-v for v in self.rz(self.model, 3, 5)], 'bone 5 mirrors bone 4')
        self.assertEqual(tired[0], tired[-1], 'the loop closes')
        self.assertTrue(all(abs(b - a) <= 25 for a, b in zip(tired, tired[1:])), 'slow follow-through, no snaps')

    def test_only_the_petals_and_the_neck_differ_from_the_donor(self):
        self.assertEqual(self.model.anims.table, self.donor.anims.table)
        self.assertEqual(changed_programs(self.donor, self.model), [0, 2, 3, 4, 27, 33, 35, 36])
        for slot in (0, 2, 3, 4):
            a = animsheet.slot_frames(self.model, NB, slot)
            b = animsheet.slot_frames(self.donor, NB, slot)
            self.assertEqual(a[2], b[2])                              # eyes and sound events
            self.assertEqual(len(a[0]), len(b[0]))
            for fa, fb in zip(a[0], b[0]):
                for bone, (pa, pb) in enumerate(zip(fa, fb)):
                    if slot == 3 and bone in (4, 5):
                        self.assertEqual(pa[:5] + pa[6:], pb[:5] + pb[6:])     # rz is the only channel that moved
                    elif bone == 3:
                        self.assertEqual(pa[:7], pb[:7])                     # only ty and tz of the head moved
                    else:
                        self.assertEqual(pa, pb)

    def test_the_neck_stays_on_the_bulb_in_every_tick_of_every_clip(self):
        from tools.models.field_animations import yokomon_neck as neck
        c = np.array(neck.base_ring(self.model))
        rest = np.array([0.0, -164.0, 0.0]) + c
        for model, limit in ((self.model, 6), (self.donor, 40)):
            worst = 0
            for slot in (0, 2, 3, 4):
                for f in animsheet.slot_frames(model, NB, slot)[0]:
                    R = np.array(mmd.rot_matrix(*f[3][3:6]), float)
                    worst = max(worst, np.abs(np.array(f[3][6:9], float) + R @ c - rest).max())
            self.assertLessEqual(worst, limit, (model is self.model, worst))
            if model is self.donor:
                self.assertGreater(worst, 25, 'the donor swings the stem off the bulb')

    def test_the_storage_budget_holds(self):
        self.assertLess(motionstorage.require(self.data, NB)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
