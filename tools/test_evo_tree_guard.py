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

    def test_new_disc_mega_shortcut(self):
        p, c = self.names['Greymon'], self.names['Phoenixmon']
        self.assertIn('Champion parent of a canon Mega', self.errors(lambda s, k: k[p].append(c)))

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
