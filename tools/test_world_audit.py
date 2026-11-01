"""Story-frontier regressions, unsafe-edge mutants, and legacy-save escape paths."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from world_audit import Edge, MOD, ROOT, World, arc_audit, audit, baseline_changes, possible, profile_state, reachable


class WorldGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()
        cls.original, cls.horizon = cls.world.graphs()

    def profile(self, name):
        return profile_state(next(p for p in self.world.policy['profiles'] if p['name'] == name))

    def test_unsafe_sewer_edge_is_detected(self):
        mutant = self.horizon + [Edge(27, 220, 1, 'True', 'test mutant', 'map')]
        failures = audit(self.world, self.original, mutant)
        self.assertTrue(any(f['profile'] == 'factory-closed' and f['screen'] == 220 and not f['allowed']
                            for f in failures))

    def test_unsafe_northern_edge_is_detected(self):
        mutant = self.horizon + [Edge(27, 165, 1, 'True', 'test mutant', 'map')]
        failures = audit(self.world, self.original, mutant)
        self.assertTrue(any(f['profile'] == 'before-regional-unlocks' and f['screen'] == 165
                            and not f['allowed'] for f in failures))

    def test_bypass_of_metalgreymon_is_detected(self):
        mutant = self.horizon + [Edge(247, 225, 0, 'True', 'test mutant', 'map')]
        failures = audit(self.world, self.original, mutant)
        self.assertTrue(any(f['profile'] == 'metalgreymon-barrier' and f['screen'] == 225
                            and not f['allowed'] for f in failures))

    def test_arrival_beyond_metalgreymon_is_detected(self):
        mutant = self.horizon + [Edge(312, 222, 1, 'True', 'wrong arrival mutant', 'map')]
        failures = audit(self.world, self.original, mutant)
        self.assertTrue(any(f['profile'] == 'metalgreymon-barrier' and f['screen'] == 225
                            and not f['allowed'] for f in failures))

    def test_no_unreviewed_early_original_areas(self):
        self.assertEqual([f for f in audit(self.world, self.original, self.horizon) if not f['allowed']], [])
        self.assertEqual(self.world.unresolved, [])
        self.assertEqual(baseline_changes(self.world, self.original), [])
        self.assertEqual([f for f in arc_audit(self.world, self.horizon) if not f['allowed']], [])

    def test_unsafe_crypt_entry_is_detected(self):
        mutant = self.horizon + [Edge(27, 307, 0, 'True', 'test mutant', 'map')]
        self.assertTrue(any(f['profile'] == 'crypt-before-root2' and f['screen'] == 307
                            and not f['allowed'] for f in arc_audit(self.world, mutant)))

    def test_drain_accepts_both_original_unlocks(self):
        edges = [e for e in self.horizon if e.source == 356 and e.target == 220]
        self.assertTrue(edges)
        for whamon in (False, True):
            for reopened in (False, True):
                with self.subTest(whamon=whamon, reopened=reopened):
                    state = {'recruited(Species.Whamon)': whamon, 'factorial_town_reopened': reopened}
                    self.assertEqual(any(possible(e.condition, state) for e in edges), whamon or reopened)

    def test_rubbish_hatch_accepts_both_original_roads(self):
        edges = [e for e in self.horizon if e.source == 353 and e.target == 165]
        self.assertTrue(edges)
        for rockslide in (False, True):
            for canyon in (False, True):
                with self.subTest(rockslide=rockslide, canyon=canyon):
                    state = {'native_forest_rockslide_cleared': rockslide, 'invisible_bridge_crossed': canyon}
                    self.assertEqual(any(possible(e.condition, state) for e in edges), rockslide or canyon)

    def test_old_saves_can_leave_both_sides(self):
        state = self.profile('before-regional-unlocks')
        walking = [e for e in self.horizon if e.kind not in ('return', 'transport')]
        for screen in (220, 356, 165, 353):
            with self.subTest(screen=screen):
                self.assertIn(109, reachable(walking, state, starts=(screen,)))
        for screen in range(317, 337):
            with self.subTest(legacy_seam_screen=screen):
                self.assertIn(109, reachable(walking, state, starts=(screen,)))

    def test_seam_does_not_open_the_north_from_early_overdell(self):
        state = self.profile('jungle-open-north-closed')
        paths = reachable(self.horizon, state)
        self.assertIn(335, paths)
        self.assertIn(317, paths)
        self.assertNotIn(78, paths)
        self.assertNotIn(165, paths)

    def test_seam_does_not_open_the_jungle_from_the_rockslide(self):
        state = self.profile('before-canyon-rumor')
        paths = reachable(self.horizon, state)
        self.assertIn(317, paths)
        self.assertIn(335, paths)
        self.assertNotIn(34, paths)

    def test_arcs_keep_their_entry_prerequisites(self):
        cases = [
            ({'root1': False}, (366, 367, 368)),
            ({'root2': False}, (307, 308)),
            ({'post_guided': False, 'bone_field_visited': False}, (305, 306)),
            ({'root3': False, 'recruited(Species.Angemon)': False,
              'engine.game_beaten': False, 'back_dimension_portal': 0}, (310, 311)),
            ({'root1': False, 'Canyon.OPEN': False, 'Canyon.CHASING': False}, (300, 301, 302, 303)),
            ({'mt_infinity_entrance_found': False}, (312, 313)),
            ({'recruited(Species.Digmon)': False, 'trigger(308)': False}, tuple(range(357, 366))),
            ({'recruited(Species.Whamon)': False}, (309,)),
        ]
        for state, screens in cases:
            with self.subTest(state=state):
                paths = reachable(self.horizon, state)
                self.assertTrue(set(screens).isdisjoint(paths))

    def test_ferry_cooldowns_still_gate_the_shore(self):
        for hurt, days, open_ in [(False, 0, False), (False, 4, False), (False, 5, True),
                                  (True, 9, False), (True, 10, True)]:
            state = {'recruited(Species.Whamon)': True, 'seadramon_chased': True,
                     'whamon_hurt': hurt, 'ferry_elapsed_days': days}
            with self.subTest(hurt=hurt, days=days):
                self.assertEqual(309 in reachable(self.horizon, state), open_)

    def test_arcs_remain_reachable_in_order(self):
        cases = [
            ({'ogre_fortress_cleared': True, 'Canyon.CHASING': True}, (300, 301, 302, 303)),
            ({'root1': True, 'Canyon.OPEN': False, 'Canyon.CHASING': False}, (300, 301, 302, 303, 366, 367, 368)),
            ({'root2': True}, (307, 308)),
            ({'post_guided': True}, (305, 306)),
            ({'recruited(Species.Angemon)': True, 'root3': False}, (310,)),
            ({'root3': True, 'recruited(Species.Angemon)': False}, (311,)),
            ({'mt_infinity_entrance_found': True, 'root1': False, 'root2': False, 'root3': False}, (312,)),
            ({'mt_infinity_entrance_found': True, 'root1': True, 'root2': True, 'root3': True}, (313,)),
            ({'recruited(Species.Digmon)': True}, tuple(range(357, 366))),
            ({'recruited(Species.Digmon)': False, 'trigger(308)': True}, tuple(range(357, 366))),
            ({'recruited(Species.Whamon)': True, 'seadramon_let_go': True,
              'seadramon_chased': False, 'whamon_hurt': False}, (309,)),
        ]
        for state, screens in cases:
            with self.subTest(state=state):
                self.assertTrue(set(screens).issubset(reachable(self.horizon, state)))

    def test_original_northern_way_around_canyon_is_preserved(self):
        state = self.profile('before-canyon-rumor')
        self.assertFalse(state['invisible_bridge_rumor_heard'])
        self.assertIn(38, reachable(self.original, state))
        self.assertIn(38, reachable(self.horizon, state))

    def test_vault_return_uses_recipe_override(self):
        for screen in (310, 311):
            edges = [e for e in self.horizon if e.source == screen and e.kind == 'map' and e.slot == 0]
            self.assertEqual([(e.target, e.entry) for e in edges], [(97, 0)])

    def test_freezing_library_jump_keeps_its_callers(self):
        edges = [e for e in self.original if e.target == 137
                 and 'libraries/s203/script.py' in e.evidence]
        self.assertTrue({89, 92, 93, 94}.issubset({e.source for e in edges}))
        self.assertTrue(all(e.condition != 'True' for e in edges))

    def test_debug_city_is_excluded_even_from_partial_frontiers(self):
        self.assertNotIn(238, reachable(self.original, {}))
        cheat = Edge(109, 238, 9, 'True', 'debug menu mutant', 'step',
                     effects=(('debug_mode', True),))
        self.assertNotIn(238, reachable([cheat], {}))

    def test_step_gates_keep_arrivals_and_mineward_exits(self):
        for name, slot, target, retreat in [('the-drain', 1, 220, 110), ('rubbish-mouth', 1, 165, 110),
                                           ('iron-hills-1', 0, 78, 111), ('descent-6', 1, 34, 110)]:
            with self.subTest(name=name):
                d = json.loads((ROOT / MOD / 'maps' / (name + '-data.json')).read_text())
                self.assertNotIn(110 + slot, d['collision'])
                self.assertIn(51, d['collision'])
                self.assertIn(retreat, d['collision'])
                self.assertEqual(d['warps'][slot]['targetMap'], target)
                w = d['warps'][slot]
                tx, tz = (w['x'] + 5000) // 100, (4999 - w['z']) // 100
                self.assertEqual(d['collision'][tz * 100 + tx], 0)


class Conditions(unittest.TestCase):
    def test_unknown_condition_never_hides_a_route(self):
        self.assertTrue(possible('has(Item.Gear) and root2', {'root2': True}))
        self.assertFalse(possible('has(Item.Gear) and root2', {'root2': False}))
        self.assertTrue(possible('root2 or has(Item.Gear)', {'root2': False}))

    def test_flag_written_before_warp_changes_the_frontier(self):
        edge = Edge(247, 312, 0, 'True', 'Devimon pays his debt', 'step',
                    effects=(('mt_infinity_devimon_beaten', True),))
        self.assertNotIn(312, reachable([edge], {'mt_infinity_devimon_beaten': False}, starts=(247,)))
        self.assertIn(312, reachable([edge], {}, starts=(247,)))


if __name__ == '__main__':
    unittest.main()
