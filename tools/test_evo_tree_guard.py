#!/usr/bin/env python3
"""Regression mutations must trip the evolution-tree guard."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evo_tree as T
from test_evo_tree import check, practical_errors


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp, cls.names, cls.table = T.load()
        cls.kids, _, _ = T.model(cls.sp)

    def errors(self, edit):
        sp, kids = copy.deepcopy(self.sp), copy.deepcopy(self.kids)
        edit(sp, kids)
        return '\n'.join(check(sp, kids, self.table))

    def test_current_tree(self):
        self.assertEqual(check(self.sp, self.kids, self.table), [])

    def test_sheet_mega_level(self):
        c = self.names['Apocalymon']
        self.assertIn('sheet Mega must be level 6',
                      self.errors(lambda s, k: s[c].update(level='ultimate')))

    def test_removed_parent_bonus(self):
        c, p = self.names['Kurisarimon'], self.names['Tentomon']
        def stale_bonus(sp, kids):
            sp[c]['evolution']['requirements']['digimon'] = p
        self.assertIn('parent bonus names a removed route', self.errors(stale_bonus))

    def test_native_story_level_is_preserved(self):
        c = self.names['Jijimon']
        self.assertIn('disc/story Mega must remain Ultimate',
                      self.errors(lambda s, k: s[c].update(level='mega')))

    def test_mega_cannot_have_a_mega_parent(self):
        p, c = self.names['MetalGarurumon'], self.names['Omnimon']
        self.assertIn('imported Mega parent must be Ultimate',
                      self.errors(lambda s, k: k[p].append(c)))

    def test_picker_retains_a_qualifying_losers_average(self):
        rows = {}
        for t, stat in ((1, 'offense'), (2, 'hp'), (3, 'mp')):
            row = dict.fromkeys(('digimon',) + T.ALL +
                                ('care', 'weight', 'discipline', 'happiness', 'battles', 'techs'), -1)
            row.update(care=0, weight=30, techs=0, flags=16)
            row[stat] = 1
            rows[t] = row
        stats = dict(hp=2000, mp=6000, offense=400, defense=100, speed=100, brain=100)
        # The engine keeps 200/count 1 after target 2 loses to 400;
        # target 3 then averages (200+600)/2, tying target 1.
        self.assertEqual(T.E.pick(10, [1, 2, 3], rows, {1: 5, 2: 5, 3: 5},
                                  stats, 0, 30, 'stats'), 1)

    def test_chain_does_not_assume_normal_gains_when_leaving_sukamon(self):
        _, reqs, levels = T.model(self.sp)
        p, c = self.names['Garbagemon'], self.names['BlackKingNumemon']
        witness = T.chain_witness(p, c, self.kids, reqs, levels, self.sp)
        self.assertIsNotNone(witness)
        self.assertNotIn(self.names['Sukamon'], witness['path'])

    def test_unapproved_specialty_exceptions_are_forbidden(self):
        table = copy.deepcopy(self.table)
        table['specialty_exceptions'] = [{'parent': 'Agumon', 'child': 'Palmon'}]
        self.assertIn('specialty exception must be a documented permitted canon route', check(self.sp, self.kids, table))

    def test_rookie_cannot_skip_champion(self):
        p, c = self.names['Agumon'], self.names['MetalGreymonVirus']
        self.assertIn('evolution level step must be +1', self.errors(lambda s, k: k[p].append(c)))

    def test_import_cannot_evolve_at_the_same_level(self):
        p, c = self.names['MegaKabuterimon'], self.names['HerculesKabuterimon']
        self.assertIn('evolution level step must be +1', self.errors(lambda s, k: k[p].append(c)))

    def test_native_step_exception_cannot_be_reused_by_an_import(self):
        def imported_copy(sp, kids):
            sp[999] = copy.deepcopy(sp[self.names['Etemon']])
            sp[999]['id'] = 999
            kids[999] = [self.names['MetalEtemon']]
        self.assertIn('evolution level step must be +1', self.errors(imported_copy))

    def test_vanilla_swap_cannot_change_level(self):
        c = self.names['Tapirmon']
        self.assertIn('vanilla_as must name a vanilla rookie',
                      self.errors(lambda s, k: s[c].update(vanilla_as=self.names['Drimogemon'])))

    def test_native_record_children_stay_in_resident_paths(self):
        for parent, child in [('Devimon', 'Myotismon'), ('Vegiemon', 'Cherrymon'),
                              ('Tyrannomon', 'MasterTyrannomon')]:
            self.assertIn(self.names[child], self.sp[self.names[parent]]['evolution']['to'])

    def test_original_battle_specialties_are_preserved(self):
        for t in (7, 11, 24, 27, 35, 53, 87):
            self.assertEqual(self.sp[t]['specialties'], T.S.disc_file(t)['specialties'])

    def test_mega_chain_uses_real_clock_and_lifetime(self):
        _, reqs, levels = T.model(self.sp)
        c = self.names['Apocalymon']
        p = self.sp[c]['evolution']['from'][0]
        witness = T.chain_witness(p, c, self.kids, reqs, levels, self.sp)
        self.assertIsNotNone(witness)
        self.assertEqual(witness['age_hours'], 366)
        self.assertEqual(witness['life_before'], 90)
        self.assertEqual(witness['life_after'], 210)

    def test_champion_dead_end(self):
        p = self.names['Baronmon']
        self.assertIn('Baronmon: 0 ultimate', self.errors(lambda s, k: k[p].clear()))

    def test_rookie_choices(self):
        p = self.names['Agumon']
        self.assertIn('Agumon: 0 champion', self.errors(lambda s, k: k[p].clear()))

    def test_special_rookie_choices(self):
        p = self.names['Kunemon']
        self.assertIn('Kunemon: 0 champion', self.errors(lambda s, k: k[p].clear()))

    def test_identical_picker_average(self):
        sp = copy.deepcopy(self.sp)
        c, sibling = self.names['Assaultmon'], self.names['Knightmon']
        target = sp[c]['evolution']['requirements']
        other = sp[sibling]['evolution']['requirements']
        for stat in T.ALL:
            target[stat] = other[stat]
        table = {'children': {'Assaultmon': {'parents': ['Snatchmon']}}}
        errors, _, _ = practical_errors(sp, self.kids, table)
        self.assertTrue(any('identical sibling picker average' in error for error in errors))

    def test_baby_dead_end(self):
        p = self.names['Koromon']
        self.assertIn('Koromon: 0 rookie', self.errors(lambda s, k: k[p].clear()))

    def test_mega_shortcut(self):
        p, c = self.names['Snatchmon'], self.names['Apocalymon']
        self.assertIn('Champion parent of a canon Mega', self.errors(lambda s, k: k[p].append(c)))

    def test_imperialdramon_shortcut(self):
        p, c = self.names['Snatchmon'], self.names['Imperialdramon']
        self.assertIn('Champion parent of a canon Mega', self.errors(lambda s, k: k[p].append(c)))

    def test_primary_mega_parent(self):
        c = self.names['Apocalymon']
        def remove_bonus(sp, kids):
            sp[c]['evolution']['requirements']['digimon'] = -1
        self.assertIn('Mega bonus must name its first listed parent', self.errors(remove_bonus))

    def test_new_disc_mega_shortcut(self):
        p, c = self.names['Greymon'], self.names['Phoenixmon']
        self.assertIn('Champion parent of a canon Mega', self.errors(lambda s, k: k[p].append(c)))

    def test_six_child_limit(self):
        p = self.names['Agumon']
        c = self.names['Lillymon']
        self.assertIn('more than six children', self.errors(lambda s, k: k[p].append(c)))

    def test_five_parent_limit(self):
        c = self.names['Zudomon']
        p = self.names['Agumon']
        self.assertIn('more than five parents', self.errors(lambda s, k: k[p].append(c)))

    def test_specialty(self):
        p, c = self.names['Agumon'], self.names['Palmon']
        self.assertIn('no shared specialty', self.errors(lambda s, k: k[p].append(c)))

    def test_wild_recolour(self):
        p = self.names['Agumon']
        c = next(t for t, s in self.sp.items() if s['name'] == 'Weedmon')
        self.assertIn('wild-only recolour', self.errors(lambda s, k: k[p].append(c)))

    def test_orphan_partner(self):
        c = self.names['Lillymon']
        def orphan(sp, kids):
            for cs in kids.values():
                if c in cs:
                    cs.remove(c)
        self.assertIn('Lillymon: no natural or documented special route', self.errors(orphan))


if __name__ == '__main__':
    unittest.main()
