"""Yokomon's petals and attached neck retain Tanemon's motion at its field cadence."""
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
from motiontailspace import interpolate_pose  # noqa: E402
from tools.models.field_animations import pace, yokomon_pace, yokomon_petals, yokomon_neck  # noqa: E402
from tools.models.babies.field_origin import center  # noqa: E402
from tools.models import battle_qa  # noqa: E402

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
        # Reconstruct the centred pre-pace recipe on the current mesh, so the
        # stride comparison includes the horizontal travel moved onto the root.
        source = parse(cls.data)
        source.anims = cls.donor.anims
        data, _ = yokomon_petals.build(source.build())
        data, _ = yokomon_neck.build(data)
        cls.source = parse(center(data, mmd.exe().skeleton[44], 477))

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

    def test_only_petals_neck_registration_and_field_cadence_differ_from_the_donor(self):
        self.assertEqual(self.model.anims.table, self.donor.anims.table)
        self.assertEqual(changed_programs(self.donor, self.model), [0, 1, 2, 3, 4, 14, 15, 16, 17, 18, 27, 33, 34, 35, 36])
        for slot in (0, 2, 3, 4):
            a = animsheet.slot_frames(self.model, NB, slot)
            b = animsheet.slot_frames(self.donor, NB, slot)
            n, ticks = len(b[0]) - 1, len(a[0]) - 1
            expected_events = pace._retimed_events(b[2], n, ticks)
            clean = lambda events: [(t, kind, {k: v for k, v in c.items() if k != 'frame'})
                                    for t, kind, c in events]
            self.assertEqual(clean(a[2]), clean(expected_events))
            for t, fa in enumerate(a[0]):
                i, rest = divmod(t * n * 4096 // ticks, 4096)
                fb = b[0][i] if not rest else interpolate_pose(b[0][i], b[0][i + 1], rest)
                for bone, (pa, pb) in enumerate(zip(fa, fb)):
                    channels = list(range(9))
                    if bone in (0, 1):
                        channels = list(range(6)) + [7]  # horizontal travel is registered to the root
                    elif slot == 3 and bone in (4, 5):
                        channels.remove(5)
                    elif bone == 3:
                        channels = list(range(7))
                    for c in channels:
                        self.assertAlmostEqual(pa[c], pb[c], delta=3, msg=(slot, t, bone, c))

    def test_field_speeds_and_stride_travel(self):
        from tools.models.audit_field import measure
        # Preserve travel at every stride phase, rather than only increasing
        # the root speed while the planted tendrils keep their old clock.
        for slot, (_, ticks, speed) in yokomon_pace.SLOTS.items():
            self.assertEqual(measure(self.model, NB, slot)['ticks'], ticks)
            self.assertAlmostEqual(measure(self.model, NB, slot)['units_per_tick'], speed, delta=.03)
            own = animsheet.slot_frames(self.model, NB, slot)[0]
            donor = animsheet.slot_frames(self.source, NB, slot)[0]
            n = len(donor) - 1
            start = donor[0][0][8]
            travel = start - donor[-1][0][8]
            for t, frame in enumerate(own):
                i, rest = divmod(t * n * 4096 // ticks, 4096)
                source = donor[i] if not rest else interpolate_pose(donor[i], donor[i + 1], rest)
                expected = start + round((int(source[0][8]) - start) * speed * ticks / travel)
                self.assertAlmostEqual(frame[0][8], expected, delta=2)
            for bone in range(1, NB):
                self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(own[0][bone], own[-1][bone])))

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

    def test_field_mesh_stays_centred_over_the_shadow(self):
        rows = battle_qa.check_field_origin(self.data, mmd.exe().skeleton[44], tolerance=.7, sid=477)
        self.assertEqual(set(rows), set(range(5)))
        self.assertTrue(all(r['verdict'] == 'pass' for r in rows.values()), rows)

    def test_the_storage_budget_holds(self):
        self.assertLess(motionstorage.require(self.data, NB)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
