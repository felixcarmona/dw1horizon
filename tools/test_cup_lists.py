#!/usr/bin/env python3
"""Every raisable species can register for at least one arena cup.

The cup lists are data blocks reached through a table of five entries per cup (text, requirement, over-level list,
eligible list, rivals). Four scripts carry their own copy (the Arena Lobby's, Beetle Land's and two libraries'); the
registration reads the copy of the script loaded at the time, so the copies must agree. Each `data(...)` block ends at its
own 0xFF; 254 ends a list early. Registration (`cupListHasType`, dget.c) matches an executable original only by its
id; a record original or a DIGI.DAT species takes the place of the originals of its level (nine or more of them in
the list, a Mega counting as an Ultimate) or of the original it borrows its effects from.

A list that begins with 253 states a rule instead (include/dw/cup_rules.h): `253, kind, value`, then the ids that enter
whatever the rule says. Kind 0 is the list and nothing else (the Version cups: the twelve Digimon of that V-Pet), 1 a
level, 2 an attribute, 3 a first specialty, 4 a Field; the rule reads the species' cup tag (species.cup_tag).
"""
import json
import re
import unittest
from pathlib import Path

import species as S

ROOT = Path(__file__).resolve().parents[1]
ZONES = ROOT / 'story/base/zones'
SCRIPT = ZONES / 'arena-lobby/s168-208-223/script'
COPIES = [ZONES / f'{z}/script' for z in ('beetle-land/s102-106', 'libraries/s209', 'libraries/s213')]
LEVELS = {'fresh': 1, 'in-training': 2, 'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}
CUPS = ('D C B A S R Version1 Version2 Version3 Version4 Version0 Fire Grapple ThunderWind Cool Nature Metalic Filth '
        'Dino Wing Animal Human Beetle Rookie Champion Ultimate Mega Vaccine Data Virus NatureSpirits DeepSavers '
        'NightmareSoldiers WindGuardians MetalEmpire VirusBusters DragonsRoar JungleTroopers Dark Holy Aqua').split()
RULE_MARK = 253
VERSION_CUPS = {'Version1': range(3, 15), 'Version2': range(17, 29), 'Version3': range(31, 43), 'Version4': range(45, 57)}


def cup_lists(text):
    """[(over-level list, eligible list)] by cup, from one view of a script holding the cup table."""
    start = text.index('shared L')    # the cup table is the last stretch of gotos before the data blocks
    data = text[start:]
    stream, labels = [], {}
    for line in data.splitlines():
        if m := re.search(r'shared (L\d+):', line):
            labels[m.group(1)] = len(stream)
        if m := re.search(r'data\(([^)]*)\)', line):
            stream += [int(x) for x in m.group(1).split(',')] + [0xFF]

    def read(label):
        o, out = labels[label], []
        while stream[o] < 0xFE:
            out.append(stream[o])
            o += 1
        return out
    entries = re.findall(r'goto (L\d+);', text[:start])[-4 * len(CUPS):]
    assert len(entries) == 4 * len(CUPS), len(entries)
    return [(read(entries[4 * c + 1]), read(entries[4 * c + 2])) for c in range(len(CUPS))]


class CupLists(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.species = {s['id']: s for s in S.load_content().values()}
        cls.lists = cup_lists((SCRIPT.with_suffix('.py')).read_text())

    def level(self, t):
        return LEVELS.get(self.species[t]['level'], 0) if t in self.species else 0

    def holds(self, lst, t):
        s = self.species[t]
        if lst[:1] == [RULE_MARK]:
            kind, value, ids = lst[1], lst[2], lst[3:]
            tag = S.cup_tag(s)
            return t in ids or {0: False, 1: (tag >> 15 & 7) == value, 2: (tag >> 10 & 3) == value,
                                3: (tag >> 19 & 15) == value, 4: bool(tag >> value & 1)}[kind]
        if t < S.NUM_ORIGINAL and not S.is_record_original(s):
            return t in lst
        level = min(self.level(t), 5)
        return sum(self.level(x) == level for x in lst) >= 9 or s.get('effects_like', t) in lst

    def entrants(self, cup):
        eligible = self.lists[CUPS.index(cup)][1]
        return [t for t, s in self.species.items() if 'partner' in s and self.level(t) >= 3 and self.holds(eligible, t)]

    def test_python_and_dws_views_hold_the_same_lists(self):
        self.assertEqual(self.lists, cup_lists(SCRIPT.with_suffix('.dws').read_text()))

    def test_every_copy_of_the_table_holds_the_same_lists(self):
        for copy in COPIES:
            for suffix in ('.py', '.dws'):
                self.assertEqual(self.lists, cup_lists(copy.with_suffix(suffix).read_text()), copy)

    def test_every_raisable_species_has_a_cup(self):
        raisable = [t for t, s in self.species.items() if 'partner' in s and self.level(t) >= 3]
        self.assertGreater(len(raisable), 200)
        none = [self.species[t]['name'] for t in sorted(raisable)
                if not any(self.holds(eligible, t) for _, eligible in self.lists)]
        self.assertEqual(none, [])

    def test_machinedramon_enters_the_metalic_cup(self):
        machinedramon = next(t for t, s in self.species.items() if s['name'] == 'Machinedramon')
        self.assertTrue(self.holds(self.lists[CUPS.index('Metalic')][1], machinedramon))

    def test_raisable_originals_are_over_level_where_ultimates_are(self):
        # D and C mark Ultimates as over-level; an Ultimate or Mega executable original is marked like them.
        for cup in ('D', 'C'):
            over = self.lists[CUPS.index(cup)][0]
            for t, s in self.species.items():
                if (t < S.NUM_ORIGINAL and not S.is_record_original(s) and 'partner' in s and self.level(t) >= 5
                        and t >= 66):
                    self.assertIn(t, over, (cup, s['name']))


    def test_a_version_cup_takes_only_its_v_pet(self):
        for cup, ids in VERSION_CUPS.items():
            self.assertEqual(sorted(self.entrants(cup)), [t for t in ids if 'partner' in self.species[t]], cup)

    def test_a_level_cup_takes_only_that_level(self):
        for cup, level in (('Rookie', 3), ('Champion', 4), ('Ultimate', 5), ('Mega', 6)):
            entrants = self.entrants(cup)
            self.assertTrue(entrants and all(self.level(t) == level for t in entrants), cup)

    def test_every_new_cup_fills_its_bracket(self):
        # the arena draws seven rivals from the species the rule takes; a level cup has only its own level to draw from
        for cup in CUPS[23:]:
            self.assertGreaterEqual(len(self.entrants(cup)), 8, cup)

    def test_a_specialty_cup_takes_every_species_of_that_first_specialty(self):
        for cup, element in (('Fire', 'fire'), ('Grapple', 'battle'), ('ThunderWind', 'air'), ('Cool', 'ice'),
                             ('Nature', 'nature'), ('Metalic', 'mech'), ('Filth', 'filth'), ('Dark', 'dark'),
                             ('Holy', 'light'), ('Aqua', 'water')):
            entrants = set(self.entrants(cup))
            for t, s in self.species.items():
                if 'partner' in s and self.level(t) >= 3 and s['specialties'][0] == element:
                    self.assertIn(t, entrants, (cup, s['name']))


if __name__ == '__main__':
    unittest.main()
