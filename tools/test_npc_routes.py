"""Route regressions: visibility, accepted ground, and deliberate corridor blocks."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_npc_routes as routes


class NpcRoutes(unittest.TestCase):
    def screen(self, number):
        return next(s for s in routes.placements() if s['screen'] == number)

    def test_day_and_night_enemies_never_overlap(self):
        for number in (319, 329):
            states = routes.visible_states(self.screen(number))
            self.assertIn((0, 1), states)
            self.assertIn((0, 2), states)
            self.assertIn((), states)  # both wild enemies beaten
            self.assertFalse(any(1 in state and 2 in state for state in states))

    def test_inherited_pickups_only_on_placement_only_screens(self):
        self.assertIn(('spawn_item', -50, 350, 0), self.screen(319)['targets'])
        self.assertFalse(self.screen(364)['targets'])  # owned resident script

    def test_stationary_npc_cannot_claim_wild_pickup_exception(self):
        s = self.screen(354)
        s['wild'][0] = False  # Gururumon becomes a persistent body
        errors = routes.check_screen(s, routes.authored_geometry(s))
        self.assertTrue(any('spawn_item' in error for error in errors), errors)

    def test_restore_old_bone_field_position_fails(self):
        s = self.screen(306)
        kind, _, _, radius = s['npcs'][0]
        s['npcs'][0] = kind, -318, -97, radius
        errors = routes.check_screen(s, routes.authored_geometry(s))
        self.assertTrue(any('cut off' in error for error in errors), errors)

    def test_new_sunken_gallery_block_fails(self):
        s = self.screen(344)
        kind, _, _, radius = s['npcs'][0]
        # A new position, distinct from the old (-550, -50) regression.
        s['npcs'][0] = kind, -500, 50, radius
        errors = routes.check_screen(s, routes.authored_geometry(s))
        self.assertTrue(any('exit/trigger' in error for error in errors), errors)

    def test_accepted_pocket_does_not_exempt_an_interaction(self):
        s = self.screen(364)
        # The east pocket is intentionally accepted only while it is empty.
        # Facing 0 opens from four collision rows below the chest.
        s['targets'].append(('spawn_chest', 700, 250, 0))
        errors = routes.check_screen(s, routes.authored_geometry(s))
        self.assertTrue(any('spawn_chest' in error and 'cut off' in error for error in errors), errors)


if __name__ == '__main__':
    unittest.main()
