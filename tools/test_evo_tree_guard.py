#!/usr/bin/env python3
"""Regression mutations must trip the evolution-tree guard."""
import copy
import json
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

    def test_native_mega_shortcuts_are_forbidden(self):
        for parent, child in [('Kabuterimon', 'HerculesKabuterimon'),
                              ('Kuwagamon', 'HerculesKabuterimon'),
                              ('Shellmon', 'HerculesKabuterimon'),
                              ('Birdramon', 'Phoenixmon'), ('Angemon', 'Phoenixmon'),
                              ('Airdramon', 'Phoenixmon'), ('Unimon', 'Phoenixmon'),
                              ('Kokatorimon', 'Phoenixmon')]:
            p, c = self.names[parent], self.names[child]
            with self.subTest(parent=parent, child=child):
                self.assertIn('Champion parent of a canon Mega',
                              self.errors(lambda s, k: k[p].append(c)))

    def test_losing_second_mega_is_a_failure(self):
        p, c = self.names['MegaKabuterimon'], self.names['GranKuwagamon']
        self.assertIn('MegaKabuterimon: 1 Mega targets; needs 2',
                      self.errors(lambda s, k: k[p].remove(c)))

    def test_native_mega_off_routes_keep_both_directions(self):
        for p, c in self.table['off_routes']['pairs']:
            if c not in (59, 60):
                continue
            self.assertIn(c, self.sp[p]['off']['evolution']['to'])
            self.assertIn(p, self.sp[c]['off']['evolution']['from'])

    def test_pair_tables_encode_every_new_rule_and_empty_padding(self):
        import balance
        import struct
        rows = json.loads(
            (T.ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionUltimate']
        pairs = list(struct.iter_unpack('<hh', balance.encode_rule_rows('evolutionUltimate', rows)))
        self.assertEqual(len(pairs), 16)
        self.assertEqual(pairs[:len(rows)], [(r['from'], r['to']) for r in rows])
        self.assertEqual(pairs[len(rows):], [(-1, -1)] * (16 - len(rows)))

    def test_timed_pair_picker_uses_first_qualifying_rule(self):
        _, reqs, levels = T.model(self.sp)
        p = self.names['KingSukamon']
        c = self.names['KingEtemon']
        first = self.names['BlackKingNumemon']
        reqs[first] = dict(reqs[c])
        stats = dict(zip(T.ALL, (5000, 5000, 500, 500, 500, 500)))
        self.assertEqual(T.E.pick(p, [first, c], reqs, levels, stats, 0,
                                 reqs[c]['weight'], 'rule', (0, 0, 100, 100)), first)

    def test_regeneration_preserves_raise_balance_at_unchanged_levels(self):
        from unittest.mock import patch
        with patch.object(T, 'resolve'):
            planned, errors = T.plan()
        self.assertEqual(errors, [])
        for t in self.sp:
            self.assertEqual(planned[t].get('partner'), self.sp[t].get('partner'))

    def test_whamon_tier_change_keeps_explicit_off_routes(self):
        for parent in (4, 46, 57):
            self.assertIn('missing explicit off route', self.errors(
                lambda s, k: s[parent]['off']['evolution'].update(to=[-1] * 6)))
        self.assertIn('canon Ultimate', self.errors(lambda s, k: s[24].update(level='champion')))

    def test_whamon_off_rookie_picker_routes(self):
        sp = copy.deepcopy(self.sp)
        for species in sp.values():
            off = species.get('off', {})
            if off:
                species['level'] = off['level']
                species.get('evolution', {}).update(off.get('evolution', {}))
        kids, reqs, levels = T.model(sp)
        kids = {p: [c for c in cs if sp[c].get('vanilla')] for p, cs in kids.items()}
        for parent in (4, 46, 57):
            self.assertIsNotNone(T.practical(parent, 24, kids, reqs, levels, sp), sp[parent]['name'])

    def test_sheet_mega_level(self):
        c = self.names['Apocalymon']
        self.assertIn('sheet Mega must be level 6',
                      self.errors(lambda s, k: s[c].update(level='ultimate')))

    def test_removed_parent_bonus(self):
        c, p = self.names['Kurisarimon'], self.names['Tentomon']
        def stale_bonus(sp, kids):
            sp[c]['evolution']['requirements']['digimon'] = p
        self.assertIn('parent bonus names a removed route', self.errors(stale_bonus))

    def test_disc_and_story_megas_are_mega(self):
        for name in ('Phoenixmon', 'Jijimon'):
            c = self.names[name]
            self.assertIn('sheet Mega must be level 6',
                          self.errors(lambda s, k: s[c].update(level='ultimate')))

    def test_mega_cannot_have_a_mega_parent(self):
        p, c = self.names['MetalGarurumon'], self.names['Omnimon']
        self.assertIn('imported Mega parent must be Ultimate',
                      self.errors(lambda s, k: k[p].append(c)))

    def test_old_average_no_longer_excludes_qualifiers(self):
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
        self.assertEqual(T.E.outcomes(10, [1, 2, 3], rows, {1: 5, 2: 5, 3: 5},
                                     stats, 0, 30, 'stats'), (1, 2, 3))

    def test_shadowed_rookie_routes_have_ordinary_picker_witnesses(self):
        _, reqs, levels = T.model(self.sp)
        cases = [
            ('Wormmon', 'Dokugumon', (1000, 1000, 100, 200, 100, 300), 3, 20),
            ('Gomamon', 'Tylomon', (1000, 1000, 100, 100, 300, 100), 0, 10),
        ]
        for parent, child, values, care, weight in cases:
            with self.subTest(parent=parent, child=child):
                p, c = self.names[parent], self.names[child]
                stats = dict(zip(T.ALL, values))
                self.assertIn(c, T.E.outcomes(p, self.kids[p], reqs, levels, stats,
                                             care, weight, 'stats', (0, 0, 100, 100)))
                # Changing a shared requirement must leave every sibling reachable.
                for other_parent, children in self.kids.items():
                    if c in children:
                        for sibling in children:
                            self.assertTrue(T.E.reachable(other_parent, sibling, children,
                                                         reqs, levels, 'stats'),
                                            (self.sp[other_parent]['name'], self.sp[sibling]['name']))

    def test_seadramon_keeps_original_winning_states(self):
        _, reqs, levels = T.model(self.sp)
        p, added = self.names['Seadramon'], self.names['WaruSeadramon']
        # Before the route repair, WaruSeadramon got its bonus for free from
        # Seadramon. Retain that baseline to catch changes to the loser's carry.
        before = copy.deepcopy(reqs)
        before[added].update(digimon=p, battles=-1)
        originals = T.S.originals().rec[p]['evoPaths']['to']
        for child in (c for c in originals if c > 0):
            with self.subTest(child=self.sp[child]['name']):
                state = T.E.canonical(p, child, reqs, levels)
                stats, care, weight, bonus = state
                self.assertIn(child, T.E.outcomes(p, self.kids[p], reqs, levels, stats,
                                                  care, weight, 'stats', bonus))
                checked = 0
                for stats, care, weight, bonus in T.E.states(
                        p, child, self.kids[p], before, levels, 'stats'):
                    self.assertIn(child, T.E.outcomes(p, self.kids[p], reqs, levels, stats,
                                                      care, weight, 'stats', bonus))
                    checked += 1
                self.assertGreater(checked, 0)
        for parent, children in self.kids.items():
            if added in children:
                self.assertIsNotNone(T.practical(parent, added, self.kids, reqs,
                                                 levels, self.sp), self.sp[parent]['name'])

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

    def test_canon_link_exception_is_narrow_and_required(self):
        for entries in ([], [{'parent': 'Tsunomon', 'child': 'Gabumon'}],
                        self.table['canon_link_exceptions'] +
                        [{'parent': 'Agumon', 'child': 'Palmon', 'reason': 'unrelated'}]):
            table = copy.deepcopy(self.table)
            table['canon_link_exceptions'] = entries
            self.assertIn('canon link allow-list must contain only documented Tsunomon -> Gabumon',
                          check(self.sp, self.kids, table))
        table['canon_link_exceptions'] = []
        self.assertIn('Tsunomon -> Gabumon: no shared specialty', check(self.sp, self.kids, table))

    def test_baby_chart_has_six_practical_targets_and_unchanged_identity(self):
        _, reqs, levels = T.model(self.sp)
        for p, s in self.sp.items():
            if s['level'] != 'in-training' or 'partner' not in s:
                continue
            self.assertEqual(len(self.kids[p]), 6, s['name'])
            for c in self.kids[p]:
                self.assertIsNotNone(T.rookie_witness(p, c, self.kids, reqs, levels, self.sp),
                                     f'{s["name"]} -> {self.sp[c]["name"]}')
        self.assertEqual(self.sp[16]['specialties'], ['air', 'ice', None])

    def test_canon_route_weight_does_not_change_koromon_or_off_mode(self):
        req = self.sp[17]['evolution']['requirements']
        self.assertEqual(T.E.target_weight(16, 17, req), 26)
        self.assertEqual(T.E.target_weight(2, 17, req), 15)
        self.assertEqual(T.E.target_weight(16, 17, req, new_digimon=False), 15)
        self.assertNotIn(17, self.sp[16]['off']['evolution']['to'])
        self.assertNotIn(16, self.sp[17]['off']['evolution']['from'])

    def test_original_baby_winning_states_at_normal_weights_stay(self):
        import itertools
        _, reqs, levels = T.model(self.sp)
        for p, old in ((2, [3, 17]), (16, [18, 57]), (30, [31, 45]), (44, [46, 4])):
            for top, weight, care in itertools.product(range(6), range(10, 21), (0, 1)):
                stats = {k: (100 if i == top else 10) * (10 if i < 2 else 1)
                         for i, k in enumerate(T.ALL)}
                before = T.E.pick(p, old, reqs, levels, stats, care, weight, 'in-training')
                self.assertEqual(T.E.pick(p, self.kids[p], reqs, levels, stats, care, weight,
                                          'in-training'), before, (p, top, weight, care))

    def test_rookie_cannot_skip_champion(self):
        p, c = self.names['Agumon'], self.names['MetalGreymonVirus']
        self.assertIn('evolution level step must be +1', self.errors(lambda s, k: k[p].append(c)))

    def test_import_cannot_evolve_at_the_same_level(self):
        p, c = self.names['MegaKabuterimon'], self.names['Zudomon']
        self.assertIn('evolution level step must be +1', self.errors(lambda s, k: k[p].append(c)))

    def test_native_step_exception_cannot_be_reused_by_an_import(self):
        def imported_copy(sp, kids):
            sp[999] = copy.deepcopy(sp[self.names['Kabuterimon']])
            sp[999]['id'] = 999
            kids[999] = [self.names['HerculesKabuterimon']]
        errors = self.errors(imported_copy)
        self.assertIn('evolution level step must be +1', errors)
        self.assertIn('Champion parent of a canon Mega', errors)

    def test_vanilla_swap_cannot_change_level(self):
        c = self.names['Tapirmon']
        self.assertIn('vanilla_as must name a vanilla rookie',
                      self.errors(lambda s, k: s[c].update(vanilla_as=self.names['Drimogemon'])))

    def test_native_record_children_stay_in_resident_paths(self):
        for parent, child in [('Devimon', 'Myotismon'), ('Vegiemon', 'Cherrymon'),
                              ('Tyrannomon', 'MasterTyrannomon')]:
            self.assertIn(self.names[child], self.sp[self.names[parent]]['evolution']['to'])

    def test_dolphmon_inherits_champion_whamon_without_changing_off_routes(self):
        s = self.sp[238]
        self.assertEqual(set(s['evolution']['from']), {217, 46, 4, 57})
        self.assertEqual(s['evolution']['requirements'], self.sp[24]['off']['evolution']['requirements'])
        self.assertEqual(s['specialties'], ['ice', 'air', None])
        self.assertIn('Blasting Spout', s['techniques'])
        champion_ice = {'Tear Drop', 'Giga Freeze', 'Ice Needle', 'Water Blit',
                        'Ice Statue', 'Winter Blast', 'Aurora Freeze', 'Aqua Magic'}
        self.assertTrue(champion_ice <= set(s['techniques']))
        for p in (217, 46, 4, 57):
            self.assertIn(238, self.kids[p])
            self.assertLessEqual(len(self.kids[p]), 6)
        _, reqs, levels = T.model(self.sp)
        for p in (217, 46, 4, 57):
            witness = T.practical(p, 238, self.kids, reqs, levels, self.sp)
            self.assertIsNotNone(witness, self.sp[p]['name'])
            self.assertEqual(witness['sessions'], 0)
        for p in (46, 4, 57):
            stats = dict(hp=1500, mp=1500, offense=150, defense=150, speed=150, brain=150)
            self.assertIn(238, T.E.outcomes(p, self.kids[p], reqs, levels, stats, 0, 40, 'stats',
                                        (0, 0, 100, 100)))
        for p in (46, 4, 57):
            self.assertIn(24, self.sp[p]['off']['evolution']['to'])
            # Legacy reverse links may remain, but the off picker excludes non-vanilla targets.
            self.assertFalse(self.sp[238].get('vanilla'))

    def test_original_battle_specialties_are_preserved(self):
        for t in (7, 11, 24, 27, 35, 53):
            self.assertEqual(self.sp[t]['specialties'], T.S.disc_file(t)['specialties'])
        self.assertEqual(self.sp[87]['specialties'], ['filth', 'nature', None])

    def test_mega_chain_uses_real_clock_and_lifetime(self):
        _, reqs, levels = T.model(self.sp)
        c = self.names['Apocalymon']
        p = self.sp[c]['evolution']['from'][0]
        witness = T.chain_witness(p, c, self.kids, reqs, levels, self.sp)
        self.assertIsNotNone(witness)
        self.assertEqual(witness['age_hours'], 390)
        self.assertEqual(witness['life_before'], 114)
        self.assertEqual(witness['life_after'], 234)

    def test_ultimate_without_mega(self):
        p = self.names['Piximon']
        self.assertIn('Piximon: 0 Mega targets; needs 2', self.errors(lambda s, k: k[p].clear()))

    def test_every_raisable_ultimate_has_a_mega_route(self):
        missing = [e for e in check(self.sp, self.kids, self.table) if 'Mega targets; needs 2' in e]
        self.assertEqual(missing, [])
        for name in ('Vademon', 'KingSukamon', 'WaruMonzaemon', 'Gigadramon'):
            self.assertIn('ultimate', self.sp[self.names[name]]['level'])

    def test_ultimate_rule_must_match_the_engine_table(self):
        table = copy.deepcopy(self.table)
        table['ultimate_rules'] = [r for r in table['ultimate_rules'] if r['from'] != 'WaruMonzaemon']
        errors = '\n'.join(check(self.sp, self.kids, table))
        self.assertIn('ultimate_rules must match evolution-rules.json evolutionUltimate', errors)

    def test_special_ultimate_chain_uses_its_champion_wait(self):
        _, reqs, levels = T.model(self.sp)
        p, c = self.names['Vademon'], self.names['HiAndromon']
        witness = T.chain_witness(p, c, self.kids, reqs, levels, self.sp)
        self.assertIsNotNone(witness)
        self.assertEqual(witness['age_hours'], 102 + 240 + 120)
        self.assertEqual(witness['life_before'], 306 - 240 + 96 - 120)

    def test_champion_dead_end(self):
        p = self.names['Baronmon']
        self.assertIn('Baronmon: 0 ultimate', self.errors(lambda s, k: k[p].clear()))

    def test_special_champion_still_needs_two_ultimates(self):
        p, c = self.names['Numemon'], self.names['KingSukamon']
        self.assertIn('Numemon: 1 ultimate', self.errors(lambda s, k: k[p].remove(c)))

    def test_disc_route_cannot_disappear(self):
        p, c = self.names['Agumon'], self.names['Greymon']
        self.assertIn('original disc route removed', self.errors(lambda s, k: k[p].remove(c)))

    def test_rookie_choices(self):
        p = self.names['Agumon']
        self.assertIn('Agumon: 0 champion', self.errors(lambda s, k: k[p].clear()))

    def test_special_rookie_choices(self):
        p = self.names['Kunemon']
        self.assertIn('Kunemon: 0 champion', self.errors(lambda s, k: k[p].clear()))

    def test_identical_stat_groups_can_both_qualify(self):
        sp = copy.deepcopy(self.sp)
        c, sibling = self.names['Assaultmon'], self.names['Datamon']
        target = sp[c]['evolution']['requirements']
        other = sp[sibling]['evolution']['requirements']
        for stat in T.ALL:
            target[stat] = other[stat]
        table = {'children': {'Assaultmon': {'parents': ['Tankmon']}}}
        errors, _, _ = practical_errors(sp, self.kids, table)
        self.assertEqual(errors, [])

    def test_baby_dead_end(self):
        p = self.names['Koromon']
        self.assertIn('Koromon: 0 rookie', self.errors(lambda s, k: k[p].clear()))

    def test_mega_shortcut(self):
        p, c = self.names['Hookmon'], self.names['Apocalymon']
        self.assertIn('Champion parent of a canon Mega', self.errors(lambda s, k: k[p].append(c)))

    def test_imperialdramon_shortcut(self):
        p, c = self.names['Hookmon'], self.names['Imperialdramon']
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
