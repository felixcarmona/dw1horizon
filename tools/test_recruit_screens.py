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


if __name__ == '__main__':
    unittest.main()
