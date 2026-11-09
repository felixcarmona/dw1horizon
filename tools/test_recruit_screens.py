"""Presence policy preserves story battles and all existing setup conditions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.dws import recruitment
from tools.dws.recruit_screens import guard_wilds, ordinary_slots, requires_unrecruited


class RecruitScreens(unittest.TestCase):
    def test_audited_wild_handlers(self):
        for screen, slots in {24: {0}, 36: {0, 1, 2, 3}, 56: {0, 1, 2},
                              59: {0}, 87: {0, 1, 2, 3}, 94: {0, 1, 2, 3}, 162: {1, 2}}.items():
            self.assertEqual(ordinary_slots(screen), slots, screen)

    def test_story_entities_are_retained(self):
        for screen in (6, 21, 45, 78, 85, 97, 222, 233, 325):
            self.assertEqual(ordinary_slots(screen), set(), screen)

    def test_or_is_not_an_unrecruited_requirement(self):
        flag = recruitment.recruit_trigger(200)
        atom = ('not', ('trig', flag))
        self.assertTrue(requires_unrecruited(('and', [atom, ('trig', 9)]), flag))
        self.assertFalse(requires_unrecruited(('or', [atom, ('trig', 9)]), flag))

    def test_guards_preserve_original_branches_and_story_loads(self):
        flag = recruitment.recruit_trigger(200)
        comp = SimpleNamespace(placements=[(24, 2, 200)], city={'presence': {24: {'npcs': [
            (2, 200, 0, ('not', ('trig', flag)))
        ]}}})
        original = ('sec24:\n    IF trigger 9, else old_end\n'
                    '    LOAD_DIGIMON 74                     ; model offset\n    SET_DIGIMON 74, 0, 1 ; wild\n'
                    '    LOAD_DIGIMON 150\n    SET_DIGIMON 150, 1, 0\n'
                    'old_end:\n    END_SECTION\nsec25:\n    END_SECTION\n')
        with recruitment.story(False):
            self.assertEqual(guard_wilds(comp, original, []), original)
        with recruitment.story(True), patch.object(recruitment, 'roster', return_value={200}):
            result = guard_wilds(comp, original, [])
        self.assertEqual(result.count(f'IF trigger {flag}, else'), 2)
        self.assertIn('IF trigger 9, else old_end', result)
        self.assertIn('    LOAD_DIGIMON 150\n    SET_DIGIMON 150, 1, 0', result)
        self.assertTrue(result.endswith('sec25:\n    END_SECTION\n'))

    def test_timed_recruit_only_hides_wilds_while_present(self):
        from tools.dws import backend, presence
        flag = recruitment.recruit_trigger(229)
        condition = ('and', [('not', ('trig', flag)), ('cmp', 'clock.hour', '>=', 20)])
        comp = SimpleNamespace(placements=[(56, 3, 229)], city={'presence': {56: {'npcs': [
            (3, 229, 0, condition)
        ]}}})
        # Include the real recruit setup as well as the original three wilds:
        # both sides must agree about who is present at every hour.
        original = ('.section 56 sec56\nsec56:\n    STORE_DATE p105\n'
                    f'    IF {backend.presence_if(condition, 56, 3)}, else recruit_end\n'
                    '    LOAD_DIGIMON 229\n    SET_DIGIMON 229, 3, 0\nrecruit_end:\n'
                    '    LOAD_DIGIMON 107\n    SET_DIGIMON 107, 0, 1\n'
                    '    SET_DIGIMON 107, 1, 1\n    SET_DIGIMON 107, 2, 1\n    END_SECTION\n')
        with recruitment.story(True):
            result = guard_wilds(comp, original, [])
        with patch.dict(presence._CACHE, {'prog': presence.Program(result)}):
            for hour in range(24):
                for recruited in (False, True):
                    st = presence.Concrete(triggers=[flag] if recruited else [], clock=(0, 0, hour, 0))
                    placements, _ = presence.run_original(56, st)
                    expected = {3: (229, 0)} if not recruited and hour >= 20 else {
                        0: (107, 1), 1: (107, 1), 2: (107, 1)}
                    self.assertEqual(placements, expected, (hour, recruited))

    def test_multiple_recruits_use_all_presence_requirements(self):
        from tools.dws import presence
        f1, f2 = (recruitment.recruit_trigger(s) for s in (229, 200))
        conditions = [
            ('and', [('not', ('trig', f1)), ('cmp', 'clock.hour', '>=', 20)]),
            ('and', [('not', ('trig', f2)), ('trig', 9)])]
        comp = SimpleNamespace(placements=[(56, 3, 229), (56, 4, 200)],
                               city={'presence': {56: {'npcs': [
                                   (3, 229, 1, conditions[0]), (4, 200, 1, conditions[1])]}}})
        original = ('.section 56 sec56\nsec56:\n'
                    '    LOAD_DIGIMON 107\n    SET_DIGIMON 107, 0, 1\n    END_SECTION\n')
        with recruitment.story(True), patch.object(recruitment, 'roster', return_value={229, 200}):
            result = guard_wilds(comp, original, [])
        with patch.dict(presence._CACHE, {'prog': presence.Program(result)}):
            for hour in (0, 12, 19, 20, 23):
                for triggers in ([], [9], [f1], [f2], [f1, 9], [f2, 9], [f1, f2, 9]):
                    st = presence.Concrete(triggers=triggers, clock=(0, 0, hour, 0))
                    placements, _ = presence.run_original(56, st)
                    waiting = any(presence.holds(c, st) for c in conditions)
                    self.assertEqual(placements, {} if waiting else {0: (107, 1)}, (hour, triggers))


if __name__ == '__main__':
    unittest.main()
