"""Regression for the Overdell tree pocket and reviewed native scenery holes."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import content
import dwmap
from maps import reach


@unittest.skipUnless((ROOT / 'extracted/MAP/MAP3/DGHA02.MAP').exists(), 'needs USA extraction')
class CemeteryPocket(unittest.TestCase):
    def setUp(self):
        self.original = dwmap.MapFile((ROOT / 'extracted/MAP/MAP3/DGHA02.MAP').read_bytes())
        self.fixed = dwmap.MapFile(self.original.build())
        self.edits = json.loads((ROOT / 'content/maps/DGHA02.json').read_text())['collision']
        content.apply_map_collision(self.fixed, self.edits, 'DGHA02')

    def test_old_partner_position_can_escape_instead_of_only_sealing_it_off(self):
        # The small broken stone below the west stump. A medium partner's
        # leading edges hit the stump and fallen roots in every heading.
        x, z, radius = -1350, -450, 190
        self.assertFalse(any(reach._step_ok(self.original, x+dx, z+dz, dx, dz, radius)
                             for dx, dz in reach._moves()))
        # Bare grass south and west must let an already stranded actor leave.
        for dx, dz in ((-50, 0), (0, -50)):
            self.assertTrue(reach._step_ok(self.fixed, x+dx, z+dz, dx, dz, radius))
        self.assertEqual(self.fixed.collision[53*100+34], 0)
        self.assertEqual(self.fixed.collision[56*100+37], 0)
        self.assertEqual(self.fixed.collision[54*100+36], 128)

    def test_shard_trap_is_solid_and_arrivals_still_connect(self):
        self.assertIn((38, 50), reach.trap_tiles(self.original))
        self.assertEqual(reach.trap_tiles(self.fixed), [])
        self.assertEqual(reach.check_arrivals(self.fixed), [])

    def test_collision_only_and_floor_loss_confined_to_stone_body_margins(self):
        original_bytes, fixed_bytes = self.original.build(), self.fixed.build()
        self.assertEqual(len(original_bytes), len(fixed_bytes))
        # Collision is the final fixed-size section. Keep camera, actors,
        # warps, foreground sprites and all other asset bytes identical.
        self.assertEqual(original_bytes[:-10000], fixed_bytes[:-10000])
        old = reach.reach(self.original)
        new = reach.reach(self.fixed)
        lost = old-new
        self.assertTrue(all(any(max(abs(reach.col(x)-tx), abs(reach.row(z)-tz)) <= 2
                                for tx, tz in ((36, 54), (38, 50)))
                            for x, z in lost))
        self.assertTrue(new-old, 'the bare grass must add walking room')


if __name__ == '__main__':
    unittest.main()
