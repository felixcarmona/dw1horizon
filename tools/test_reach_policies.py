"""Pin geometry boundaries and the distinct map-author/walking seed policies."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MAP = module('map_reach_contract', 'tools/maps/reach.py')
WALK = SimpleNamespace(**{name: getattr(MAP, name) for name in ('tdiv', 'col', 'row')}, reach=MAP.from_spawn_coordinates)
BASE = module('recipe_mapbase_contract', 'story/mods/what-the-island-forgot/maps/mapbase.py')
STORY = SimpleNamespace(**{name: getattr(MAP, name) for name in ('tdiv', 'col', 'row')}, reach=BASE.reachable)


def scene(used=True, x=0, z=0, blocked=False, y=0):
    collision = bytearray([128] * 10000)
    if not blocked:
        for tx in range(45, 56):
            for tz in range(44, 55):
                collision[tz * 100 + tx] = 0
    return SimpleNamespace(collision=collision,
                           warps=[dict(targetMap=1 if used else -1, x=x, y=y, z=z)])


class ReachPolicies(unittest.TestCase):
    def test_negative_c_division_and_tile_edges(self):
        for mod in (MAP, WALK, STORY):
            self.assertEqual([mod.tdiv(v) for v in (-101, -100, -99, -1, 0, 99, 100)], [-1, -1, 0, 0, 0, 0, 1])
            self.assertEqual([mod.col(v) for v in (-101, -100, -99, -1, 0, 99, 100)], [48, 48, 49, 49, 50, 50, 51])
            self.assertEqual([mod.row(v) for v in (-101, -100, -99, -1, 0, 99, 100)], [51, 51, 50, 50, 49, 49, 48])

    def test_unused_warp_coordinates_are_walk_seeds_only(self):
        m = scene(used=False, x=10)
        self.assertEqual(MAP.reach(m), set())
        self.assertTrue(WALK.reach(m))
        self.assertEqual(WALK.reach(m), STORY.reach(m))

    def test_blocked_starts_retained_only_by_walk_policy(self):
        m = scene(blocked=True)
        self.assertEqual(MAP.reach(m), set())
        self.assertEqual(WALK.reach(m), {(0, 0)})
        self.assertEqual(STORY.reach(m), {(0, 0)})

    def test_used_free_arrival_matches_all_three(self):
        m = scene()
        self.assertEqual(MAP.check_arrivals(m), [])
        self.assertEqual(MAP.reach(m), WALK.reach(m))
        self.assertEqual(MAP.reach(m), STORY.reach(m))

    def test_blocked_height_and_bouncing_diagnostics(self):
        m = scene(blocked=True, y=1)
        self.assertEqual(MAP.check_arrivals(m), ['arrival 0: blocked or outside map', 'arrival 0: nonzero warp height 1'])
        m = scene()
        m.collision[49 * 100 + 50] = 110
        self.assertIn('arrival 0: stands on or beside its own exit', MAP.check_arrivals(m))

    def test_npc_collision_uses_inclusive_square_and_both_radii(self):
        m = scene()
        points = MAP.reach(m, footprints=[(200, 0, 50)])
        self.assertIn((40, 0), points)
        self.assertNotIn((50, 0), points)     # 100 tamer + 50 NPC, inclusive edge
        self.assertNotIn((350, 150), points) # square corner, outside a circle
        self.assertIn((360, 150), points)
        self.assertIn((200, 160), points)
        self.assertIn((200, 0), MAP.reach(m)) # absent NPC leaves its ground open

    def test_disconnected_arrivals_do_not_union_components(self):
        m = scene()
        for tx in range(70, 81):
            for tz in range(44, 55):
                m.collision[tz * 100 + tx] = 0
        m.warps.append(dict(targetMap=2, x=2500, y=0, z=0))
        self.assertIn('arrival 1: unreachable from arrival 0', MAP.check_arrivals(m))


class RecipeArrivalPolicy(unittest.TestCase):
    def test_recipe_policy_keeps_height_and_connectivity_out_of_validation(self):
        m = scene(y=100)
        m.warps.append(dict(targetMap=2, x=2500, y=0, z=0))
        m.collision[49 * 100 + 75] = 0
        self.assertIsNone(BASE.check_arrivals(m, 'recipe'))
        self.assertIn('arrival 0: nonzero warp height 100', MAP.check_arrivals(m))

    def test_recipe_policy_retains_author_diagnostics(self):
        with self.assertRaisesRegex(SystemExit, r'recipe: the arrival of warp 0 at tile \(50,49\) is not free'):
            BASE.check_arrivals(scene(blocked=True), 'recipe')
        m = scene()
        m.collision[49 * 100 + 51] = 110
        with self.assertRaisesRegex(SystemExit, 'stands on or beside its own exit tiles'):
            BASE.check_arrivals(m, 'recipe')

    def test_recipe_policy_skips_unused_warps(self):
        self.assertIsNone(MAP.check_recipe_arrivals(scene(used=False, blocked=True, y=100)))


if __name__ == '__main__':
    unittest.main()
