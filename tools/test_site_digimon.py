#!/usr/bin/env python3
"""The site's Digimon guide: the generator's output, whose requirements say
what the in-game guide's card says (chartCardBuild, game_menu.c).

Usage: python3 tools/test_site_digimon.py
"""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import site_digimon as G
import species as S

SCORE = {'weightTolerance': 5, 'hpMpDiv': 10}


def row(**over):
    r = dict.fromkeys(S.REQ_KEYS, -1)
    r.update(flags=0)
    r.update(over)
    return r



class Card(unittest.TestCase):
    def test_baby_ii_is_automatic(self):
        self.assertEqual(G.requirements(row(), 'in-training', SCORE), 'automatic')

    def test_rookie_asks_for_the_highest_stat(self):
        q = G.requirements(row(digimon=2, hp=1, mp=1, offense=1, care=0, weight=15), 'rookie', SCORE)
        self.assertEqual(q, {'mistakes': None, 'weight': [10, 20], 'top': ['hp', 'mp', 'offense'], 'bonus': {'from': 2}})

    def test_rookie_bonus_that_always_holds_is_any(self):
        self.assertIsNone(G.requirements(row(digimon=44, speed=1, care=0, weight=15, battles=-2), 'rookie', SCORE)['bonus'])
        self.assertIsNone(G.requirements(row(digimon=44, speed=1, care=0, weight=15, techs=0), 'rookie', SCORE)['bonus'])

    def test_hp_and_mp_are_shown_times_ten_and_mistakes_are_a_minimum_without_the_flag(self):
        q = G.requirements(row(digimon=88, offense=400, speed=300, brain=400, care=10, weight=30, techs=35), 'ultimate', SCORE)
        self.assertEqual(q, {'mistakes': [10], 'weight': [25, 35], 'stats': {'offense': [400], 'speed': [300], 'brain': [400]},
                             'bonus': {'from': 88, 'techs': [35]}})
        q = G.requirements(row(hp=700, mp=600, care=3, weight=70, discipline=95, battles=100, flags=0x10), 'ultimate', SCORE)
        self.assertEqual(q['mistakes'], [0, 3])
        self.assertEqual(q['stats'], {'hp': [7000], 'mp': [6000]})
        self.assertEqual(q['bonus'], {'discipline': [95], 'battles': [100]})

    def test_flag_one_makes_battles_a_maximum(self):
        q = G.requirements(row(offense=100, care=5, weight=30, battles=5, flags=1), 'champion', SCORE)
        self.assertEqual(q['bonus'], {'battles': [0, 5]})
        q = G.requirements(row(offense=100, care=0, weight=30, battles=0, flags=0x11), 'champion', SCORE)
        self.assertEqual((q['mistakes'], q['bonus']), ([0, 0], {'battles': [0, 0]}))

    def test_no_stat_asked_for_is_any(self):
        self.assertIsNone(G.requirements(row(care=3, weight=30), 'champion', SCORE)['stats'])


class Guide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = G.guide()
        cls.by = {x['id']: x for x in cls.g['digimon']}

    def test_is_the_chart(self):
        allsp = S.load_content()
        members = {t for t, s in allsp.items() if t > 0 and 'partner' in s}
        self.assertEqual(set(self.by), members)
        self.assertEqual(len(self.by), len(self.g['digimon']))

    def test_rule_constants(self):
        self.assertEqual(self.g['pass'], 3)

    def test_from_is_the_inverse_of_to(self):
        for t, x in self.by.items():
            for c in x['to']: self.assertIn(t, self.by[c]['from'])
            for p in x['from']: self.assertIn(t, self.by[p]['to'])

    def test_automatic_is_only_a_fresh_to_its_baby_ii(self):
        with open(G.RULES) as f: fresh = {(r['from'], r['to']) for r in json.load(f)['evolutionFresh']}
        auto = {(p, t) for t, x in self.by.items() if x.get('req') == 'automatic' for p in x['from']}
        self.assertEqual(auto, fresh)

    def test_only_a_species_without_parents_has_no_requirements(self):
        for x in self.by.values(): self.assertEqual('req' in x, bool(x['from']), x['name'])

    def test_rookies_have_a_stat_and_others_do_not(self):
        for x in self.by.values():
            q = x.get('req')
            if isinstance(q, dict):
                self.assertEqual('top' in q, x['level'] == 'rookie', x['name'])
                if 'top' in q: self.assertTrue(q['top'], x['name'])

    def test_bonus_parent_is_a_real_parent_and_never_empty(self):
        for x in self.by.values():
            b = x.get('req') if isinstance(x.get('req'), dict) else {}
            if b and b['bonus'] is not None:
                self.assertTrue(b['bonus'], x['name'])
                if 'from' in b['bonus']: self.assertIn(b['bonus']['from'], x['from'], x['name'])

    def test_known_rows(self):
        names = {x['name']: x for x in self.g['digimon']}
        agumon = names['Agumon']
        self.assertEqual(agumon['req']['bonus'], {'from': names['Koromon']['id']})
        self.assertEqual(agumon['req']['weight'], [10, 20])
        self.assertIn(names['Elecmon']['id'], names['IceLeomon']['from'])      # only a "to" of the parent's row says so
        self.assertEqual(names['WereGarurumon']['from'], [names['Garurumon']['id']])

    def test_every_ultimate_rule_is_a_route(self):
        with open(G.RULES) as f: rules = json.load(f)
        self.assertTrue(rules['evolutionUltimate'])
        for r in rules['evolutionUltimate']:
            self.assertIn(r['to'], self.by[r['from']]['to'])
            self.assertIn(r['from'], self.by[r['to']]['from'])

    def test_machinedramon_has_its_route_and_its_requirements(self):
        names = {x['name']: x for x in self.g['digimon']}
        x = names['Machinedramon']
        self.assertEqual(x['from'], [names['Megadramon']['id'], names['Gigadramon']['id']])
        self.assertEqual(x['req'], {'mistakes': [0, 3], 'weight': [65, 75],
                                    'stats': {'hp': [7000], 'mp': [6000], 'offense': [600], 'defense': [600], 'speed': [400], 'brain': [400]},
                                    'bonus': {'discipline': [95], 'battles': [100]}, 'after': 48})
        self.assertEqual([y['name'] for y in self.g['digimon'] if isinstance(y.get('req'), dict) and 'after' in y['req']], ['Machinedramon'])

    def test_new_is_every_species_the_original_game_does_not_raise(self):
        allsp = S.load_content()
        for t, x in self.by.items(): self.assertEqual(x['new'], not allsp[t].get('vanilla'), x['name'])
        self.assertEqual(sum(x['new'] for x in self.by.values()), 218)
        self.assertEqual(sum(x['new'] and t >= S.NUM_ORIGINAL for t, x in self.by.items()), 175)

    def test_technique_names_are_the_games(self):
        for x in self.by.values():
            for m in x['techniques']: self.assertNotRegex(m, r'\(\d+\)$')
            self.assertEqual(len(x['techniques']), len(set(x['techniques'])))

    def test_text_only(self):
        keys = {'id', 'name', 'level', 'attribute', 'new', 'from', 'to', 'req', 'techniques'}
        for x in self.by.values(): self.assertLessEqual(set(x), keys)


if __name__ == '__main__':
    unittest.main()
