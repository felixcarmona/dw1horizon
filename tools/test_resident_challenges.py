"""Resident challenges: content/tables/resident-challenges.json, the executable table it becomes, and the story that serves it."""
import json
import re
import struct
import unittest

from tools import city_residents as city
from tools.dws.py import naming

MOD = city.ROOT / 'story/mods/what-the-island-forgot'
LANGS = ('ca', 'de', 'es', 'fr', 'it', 'ja', 'pt-br', 'zh-hans')
BITS_CAP = 4000          # one challenge a day pays at most this much on top of the battle's own bits


class ResidentChallenges(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(city.CHALLENGES.read_text())
        self.rows = city.challenge_rows(self.doc)

    def test_table_bytes(self):
        data = city.challenge_table(self.doc)
        v = struct.unpack(f'<{len(data) // 2}h', data)
        self.assertEqual(len(v), city.CHALLENGE_HEAD + city.CHALLENGE_ROW * city.CHALLENGE_MAX)
        self.assertEqual(v[:city.CHALLENGE_HEAD], (0, 25, 1, 0, 15, 783, 784, 239, 20, 8, 0))
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
        for i, r in enumerate(self.rows):
            row = v[city.CHALLENGE_HEAD + city.CHALLENGE_ROW * i:][:city.CHALLENGE_ROW]
            w = species[r['species']]['wild']
            self.assertEqual(row, (r['species'], w['hp'], w['mp'], w['off'], w['def'], w['speed'], w['brain']))
        self.assertEqual(set(v[city.CHALLENGE_HEAD + city.CHALLENGE_ROW * len(self.rows):]), {-1})

    def test_save_numbers_are_the_story_lock(self):
        lock = json.loads((MOD / 'save.lock').read_text())
        save = self.doc['save']
        self.assertEqual(lock['vars']['challenger'], save['challengerVar'])
        self.assertEqual([lock['vars']['challenge_bag'], lock['vars']['challenge_bag2']], save['bagVars'])
        self.assertEqual(lock['flags']['challenge_won'], save['wonFlag'])
        self.assertEqual(lock['flags']['challenge_tried'], save['triedFlag'])
        self.assertIn(f"CHALLENGE_ARMED = {save['armedPstat']}\n", (MOD / 'state.py').read_text())

    def test_story_serves_every_row(self):
        state = (MOD / 'state.py').read_text()
        items = naming.enum_members('item')
        for i, r in enumerate(self.rows, 1):
            const = 'CH_' + r['name'].upper()
            self.assertIn(f'{const} = {i}\n', state, r['name'])
            src = (MOD / r['story']).read_text()
            self.assertIn(f"at=({r['site']['at'][0]}, {r['site']['at'][1]})", src, r['name'])
            self.assertIn(f"give(Item.{items[r['item']]})", src, r['name'])
            self.assertIn(f"give(bits={r['bits']})", src, r['name'])
            self.assertLessEqual(r['bits'], BITS_CAP, r['name'])
            for x, z in r['exit']:
                self.assertIn(f'run({x}, {z})', src, r['name'])
            for name in r['text'].values():
                self.assertIn(f't("{name}")', src, r['name'])
            if r['home']:
                self.assertIn(f'challenger == {const} and not challenge_won', (MOD / r['home']).read_text(), r['name'])

    def test_lines_in_every_language(self):
        names = {'challenge.home', 'challenge.yes', 'challenge.no'} | {n for r in self.rows for n in r['text'].values()}
        for lang in ('en',) + LANGS:
            bank = json.loads((MOD / f'text/{lang}.json').read_text())
            self.assertEqual(sorted(names - set(bank)), [], lang)

    def test_every_stage_has_challengers(self):
        """Stage rule same-or-lower: a Rookie partner and up always has a few residents who can go out."""
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
        levels = [city.LEVELS[species[r['species']]['level']] for r in self.rows]
        for stage in ('rookie', 'champion', 'ultimate', 'mega'):
            self.assertGreaterEqual(sum(lv <= city.LEVELS[stage] for lv in levels), 3, stage)


if __name__ == '__main__':
    unittest.main()
