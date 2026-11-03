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

    def test_one_tile_notch_is_a_trap(self):
        # Screen 361's shape: a strip one tile wide between a desk (column 49) and a chair (51-52, rows 51-52). A
        # tamer standing in it cannot step anywhere; no walk from the arrival reaches it, so blocking takes no floor.
        m = scene()
        for tx, tz in ((49, 52), (49, 53), (49, 54), (51, 51), (52, 51), (51, 52), (52, 52), (50, 54)):
            m.collision[tz * 100 + tx] = 128
        self.assertEqual(MAP.trap_tiles(m), [(50, 52), (50, 53)])
        self.assertIn('trap tile 50,52: the tamer could never move again there', MAP.check_arrivals(m))
        with self.assertRaises(SystemExit):
            MAP.check_recipe_arrivals(m, 'recipe')
        before = MAP.reach(m)
        m.collision[52 * 100 + 50] = m.collision[53 * 100 + 50] = 128
        self.assertEqual(MAP.trap_tiles(m), [])
        self.assertEqual(MAP.check_arrivals(m), [])
        self.assertEqual(MAP.reach(m), before)

    def test_floor_with_dead_wall_corners_is_not_a_trap(self):
        self.assertEqual(MAP.trap_tiles(scene()), [])
        m = scene()
        for tx, tz in ((49, 52), (49, 53), (49, 54), (51, 51), (52, 51), (51, 52), (52, 52), (50, 54)):
            m.collision[tz * 100 + tx] = 128
        m.collision[52 * 100 + 50] = m.collision[53 * 100 + 50] = 110   # an exit warps whoever stands on it
        self.assertEqual(MAP.trap_tiles(m), [])

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


class PickupReach(unittest.TestCase):
    """tamer.c checkItemPickup / checkChestCollision: the tamer's tile within one of the pickup's, both ways."""
    def test_engine_tile_of_a_position(self):
        self.assertEqual([MAP.model_tile(v, 0)[0] for v in (-101, -100, -1, 0, 99, 100)], [48, 48, 49, 50, 50, 51])
        self.assertEqual([MAP.model_tile(0, v)[1] for v in (-101, -100, -1, 0, 1, 100)], [51, 51, 50, 50, 49, 48])

    def test_open_floor_passes(self):
        self.assertEqual(MAP.check_pickups(scene(), [('mushroom', (50, 49))]), [])

    def test_item_in_rock_fails_even_beside_the_floor(self):
        # Screen 314's spot 237: the item's own tile was rock, picked up from three tiles of the floor beside it.
        m = scene()
        m.collision[49 * 100 + 56] = 128
        errors = MAP.check_pickups(m, [('rock', (56, 49)), ('exit', (50, 49))])
        self.assertEqual(errors, ['rock: item at tile 56,49 lies on collision 128, not plain floor'])
        m.collision[49 * 100 + 50] = 112
        self.assertIn('exit: item at tile 50,49 lies on collision 112, not plain floor', MAP.check_pickups(m, [('exit', (50, 49))]))

    def test_one_tile_notch_and_unreachable_island_fail(self):
        # A free tile the body box cannot enter (a notch one tile wide) and floor no walk reaches.
        m = scene()
        m.collision[49 * 100 + 56] = 0
        for tx in range(60, 66):
            for tz in range(44, 55):
                m.collision[tz * 100 + tx] = 0
        errors = MAP.check_pickups(m, [('notch', (56, 49)), ('island', (62, 49))])
        self.assertEqual(len(errors), 2)
        self.assertRegex(errors[0], r'notch: item at tile 56,49 is picked up from \d+ reachable points \(0 on its own tile')
        self.assertIn('island: item at tile 62,49 is picked up from 0 reachable points', errors[1])

    def test_screen_entered_by_script_seeds_from_its_spawn(self):
        self.assertEqual(MAP.check_pickups(scene(used=False, x=10), [('ferry', (50, 49))]), [])

    def test_chest_opens_four_tiles_in_front_with_its_own_block(self):
        # spawnChest blocks tiles 48-51 x 44-47 for a chest at tile (50, 46); facing 0 opens from (50, 50).
        self.assertEqual(MAP.check_pickups(scene(), chests=[('south', (0, 300), 0)]), [])
        errors = MAP.check_pickups(scene(), chests=[('north', (0, 300), 2048)])
        self.assertEqual(errors, ['north: chest at 0,300 opens from tile 50,42: 0 reachable points there (at least 300)'])
        self.assertIn('no opening tile', MAP.check_pickups(scene(), chests=[('odd', (0, 300), 512)])[0])


class PickupGate(unittest.TestCase):
    """tools/maps/check_pickups.py: the registry's spots where they lie, and a new screen's story pickups."""
    def test_registry_spots_and_story_pickups(self):
        import json, sys, tempfile
        sys.path.insert(0, str(ROOT / 'tools' / 'maps'))
        import check_pickups as C
        with tempfile.TemporaryDirectory() as tmp:
            registry, story = Path(tmp) / 'spots.json', Path(tmp) / 'room.py'
            registry.write_text(json.dumps(dict(format=1, spots=[
                dict(id=0, screen=0, tile=[56, 49]),                        # an original screen: not ours to check
                dict(id=1, screen=314, tile=[56, 49], at=[50, 49]),         # placed on the floor
                dict(id=2, screen=314, tile=[49, 40])])))                   # the script's tile: rock here
            story.write_text('room = new_screen(314, map="ROOM.MAP")\n@room.on_enter\ndef enter():\n'
                             '    spawn_item(Item.Meat, at=(-150, -250))\n'
                             '    spawn_chest(Item.Meat, at=(0, 300), opened=f, facing=2048)\n')
            maps = {314: ('ROOM', scene)}
            count, errors = C.run(maps, [str(story)], registry)
            self.assertEqual(count, 4)
            self.assertEqual(len(errors), 2)
            self.assertIn('ROOM: screen 314 ground spot 2: item at tile 49,40 lies on collision 128', errors[0])
            self.assertIn('room.py:5 spawn_chest: chest at 0,300 opens from tile 50,42', errors[1])
            count, errors = C.run({}, [str(story)], registry)
            self.assertIn('screen 314: ground spots registered but no map to check them on', errors)


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
