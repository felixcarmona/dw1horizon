"""Battle-ready moves for story NPCs copied from noncombat map entries."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import dwmap
from dws import backend


class BattleMoves(unittest.TestCase):
    def test_recruit_placements_from_noncombat_spore_area_templates(self):
        root = Path(__file__).resolve().parents[1]
        cases = ((233, 'MIHA05', 243, 1000, -1000), (21, 'MIHA03', 263, -450, 100))
        for screen, name, species, x, z in cases:
            with self.subTest(species=species):
                rows = json.loads((root / 'content/maps' / (name + '.json')).read_text())['digimon']
                entries = [dict(type=0, posX=r['at'][0], posZ=r['at'][1],
                                aiSections=r['ai'], waypoints=r['path'],
                                **{f'move{i}': r['moves'][i] for i in range(4)},
                                **{f'prio{i}': r['prios'][i] for i in range(4)}) for r in rows]
                model = SimpleNamespace(digimon=entries, warps=[], collision=bytes(10000))
                entry = backend.new_slot_entry(model, screen, len(entries), species,
                                               dict(posX=x, posZ=z, still=True, mp=2000),
                                               None, None, dwmap)
                self.assertEqual(entry['currentMP'], 2000)
                self.assertEqual([entry[f'move{i}'] for i in range(4)], [46, 47, 48, 255])
                self.assertTrue(all(entry[f'prio{i}'] > 0 for i in range(3)))
                self.assertEqual(entry['prio3'], 0)

    def assign(self, species, moves, priorities):
        entry = {f'move{i}': value for i, value in enumerate(moves)}
        entry.update({f'prio{i}': value for i, value in enumerate(priorities)})
        backend.set_moves(entry, species, None)
        return ([entry[f'move{i}'] for i in range(4)],
                [entry[f'prio{i}'] for i in range(4)])

    def test_starmon_inherits_noncombat_unimon_priorities(self):
        # MIHA05's original Unimon entry has no moves and four zero priorities.
        moves, priorities = self.assign(243, [255] * 4, [0] * 4)
        self.assertEqual(moves, [46, 47, 48, 255])
        self.assertTrue(all(p > 0 for p in priorities[:3]))
        self.assertEqual(priorities[3], 0)

    def test_existing_battle_preferences_survive_replacement(self):
        self.assertEqual(self.assign(243, [46, 47, 48, 255], [60, 30, 10, 0]),
                         ([46, 47, 48, 255], [60, 30, 10, 0]))

    def test_existing_empty_slot_idle_weight_survives_replacement(self):
        self.assertEqual(self.assign(243, [46, 47, 48, 255], [60, 30, 0, 10]),
                         ([46, 47, 48, 255], [60, 30, 0, 10]))

    def test_priority_on_a_removed_move_cannot_disable_remaining_attacks(self):
        with patch.dict(backend.DIGI_DATA, {999: {'moves': '2'}}):
            moves, priorities = self.assign(999, [46, 47, 48, 49], [0, 0, 0, 100])
        self.assertEqual(moves, [46, 255, 255, 255])
        self.assertGreater(priorities[0], 0)
        self.assertEqual(priorities[1:], [0, 0, 0])

    def test_noncombat_species_keeps_no_attacks(self):
        with patch.dict(backend.DIGI_DATA, {999: {'moves': ''}}):
            self.assertEqual(self.assign(999, [46, 47, 48, 255], [40, 30, 30, 0]),
                             ([255] * 4, [40, 30, 30, 0]))


if __name__ == '__main__':
    unittest.main()
