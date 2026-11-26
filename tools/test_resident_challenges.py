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
        self.assertEqual(len(data), 154)                     # tools/balance.py TABLES residentChallenges
        v = struct.unpack(f'<{len(data) // 2}h', data)
        self.assertEqual(len(v), city.CHALLENGE_HEAD + city.CHALLENGE_MAX)
        self.assertEqual(v[:city.CHALLENGE_HEAD], (10, 15, 784, 8, 783))
        fight = city.challenge_fight_table(self.doc)                 # tools/balance.py TABLES residentChallengeFight
        self.assertEqual(struct.unpack('<4h', fight), (25, 1, 1, 239))
        rows = v[city.CHALLENGE_HEAD:][:len(self.rows)]
        self.assertEqual(tuple(x & city.CHALLENGE_SPECIES for x in rows), tuple(r['species'] for r in self.rows))
        species = {d['id']: d for p in (city.ROOT / 'content/species').glob('*.json') for d in [json.loads(p.read_text())]}
        self.assertEqual(tuple(x >> city.CHALLENGE_LEVEL_SHIFT for x in rows),     # the level the daily pick compares
                         tuple(city.LEVELS[species[r['species']]['level']] for r in self.rows))
        self.assertEqual(set(v[city.CHALLENGE_HEAD + len(self.rows):]), {-1})

    def test_site_npcs_carry_the_floor(self):
        """Every row's site NPC (the one its fight uses) declares the challenge's floor: the sheet x (100 + sheetPercent)
        / 100, or, for the residents fought by their recruit NPC, that fight's own six stats."""
        recruit = set(city.CHALLENGE_RECRUIT_STATS)
        for r in self.rows:
            src = (MOD / r['story']).read_text()
            decl = [m.group(0) for m in re.finditer(r'^(\w+) = \w+\.npc\(Species\.\w+(?:.*\n\s+)*?.*\)$', src, re.M)
                    if re.search(rf"== CH_{r['name'].upper()}\b", m.group(0))]
            self.assertEqual(len(decl), 1, r['name'])
            have = {k: int(v) for k, v in re.findall(r'\b(hp|mp|offense|defense|speed|brain)=(\d+)', decl[0])}
            self.assertEqual(len(have), 6, r['name'])
            want = city.challenge_site_stats(r, self.doc)
            self.assertEqual(want is None, r['name'] in recruit, r['name'])
            if want is not None:
                self.assertEqual(have, want, r['name'])
            recruit.discard(r['name'])
        self.assertFalse(recruit, 'CHALLENGE_RECRUIT_STATS names a resident with no row')

    def test_pools(self):
        """The new pool is Horizon's own species (112 and up), the original pool the game's; a row in the wrong pool
        is refused."""
        self.assertEqual({r['pool'] for r in self.rows}, {'original', 'new'})
        for r in self.rows:
            self.assertEqual(r['pool'] == 'new', r['species'] >= 112, r['name'])
        r = next(r for r in self.doc['residents'] if r['pool'] == 'new'); r['pool'] = 'original'
        with self.assertRaises(ValueError):
            city.challenge_table(self.doc)

    def test_pools_need_their_own_save_numbers(self):
        self.doc['save']['newTriedFlag'] = self.doc['save']['triedFlag']
        with self.assertRaises(ValueError):
            city.challenge_table(self.doc)

    def test_negative_sheet_percent_refused(self):
        self.doc['rule']['sheetPercent'] = -10
        with self.assertRaises(ValueError):
            city.challenge_table(self.doc)

    def test_floor_is_wild_or_base(self):
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
        for r in self.rows:
            self.assertEqual('base' in r, species[r['species']].get('wild') is None, r['name'])
        r = next(r for r in self.doc['residents'] if 'base' not in r and r['name'] not in city.CHALLENGE_RECRUIT_STATS)
        r['base'] = dict(species[r['species']]['wild'])
        with self.assertRaises(ValueError):
            city.challenge_site_stats(r, self.doc)

    def test_save_numbers_are_the_story_lock(self):
        lock = json.loads((MOD / 'save.lock').read_text())
        save = self.doc['save']
        self.assertEqual(lock['vars']['challenger'], save['challengerVar'])
        self.assertNotIn('challenge_bag', ' '.join(lock['vars']))   # the bag is in saved wide registers, not story vars
        self.assertEqual(lock['vars']['new_challenger'], save['newChallengerVar'])
        self.assertEqual(lock['flags']['challenge_tried'], save['triedFlag'])
        self.assertEqual(lock['flags']['new_challenge_tried'], save['newTriedFlag'])
        self.assertIn('CHALLENGE_BEATEN = 128\n', (MOD / 'state.py').read_text())   # mod_rules.h MOD_CHALLENGE_BEATEN
        self.assertIn(f"CHALLENGE_ARMED = {save['armedPstat']}\n", (MOD / 'state.py').read_text())

    def test_story_serves_every_row(self):
        state = (MOD / 'state.py').read_text()
        items = naming.enum_members('item')
        for i, r in enumerate(self.rows, 1):
            const = 'CH_' + r['name'].upper()
            var = 'new_challenger' if r['pool'] == 'new' else 'challenger'
            self.assertIn(f'{const} = {i}\n', state, r['name'])
            src = (MOD / r['story']).read_text()
            self.assertIn(f'alone={var} == {const}', src, r['name'])
            self.assertIn(f'{var}.add(CHALLENGE_BEATEN)', src, r['name'])
            self.assertIn(f"pstat(CHALLENGE_ARMED).set({2 if r['pool'] == 'new' else 1})", src, r['name'])
            self.assertIn(f"at=({r['site']['at'][0]}, {r['site']['at'][1]})", src, r['name'])
            self.assertIn(f"give(Item.{items[r['item']]})", src, r['name'])
            self.assertIn(f"give(bits={r['bits']})", src, r['name'])
            self.assertLessEqual(r['bits'], BITS_CAP, r['name'])
            for x, z in r['exit']:
                self.assertIn(f'run({x}, {z})', src, r['name'])
            for name in r['text'].values():
                self.assertIn(f't("{name}")', src, r['name'])
            if r['home']:
                self.assertRegex((MOD / r['home']).read_text(), rf'\b{var} == {const}\b', r['name'])

    def test_lines_in_every_language(self):
        names = {'challenge.home', 'challenge.yes', 'challenge.no'} | {n for r in self.rows for n in r['text'].values()}
        for lang in ('en',) + LANGS:
            bank = json.loads((MOD / f'text/{lang}.json').read_text())
            self.assertEqual(sorted(names - set(bank)), [], lang)

    def test_yuramon_riddles_are_the_hint_rows(self):
        """Yuramon's after-ending talk jumps to the library with a riddle (who, where) for every row marked `hint` and for no
        other, tested on its own pool's var, in every language."""
        talk = (MOD / 'arcs/rumours/yuramon.py').read_text()
        self.assertIn('jump_to_script(210, 1)', talk[talk.index('def the_day_rumours'):])
        src = (MOD / 'arcs/rumours/yuramon-riddles.py').read_text()
        self.assertIn('@lib.section(1,', src)
        talk = src[src.index('def the_day_rumours'):]
        told = re.findall(r'(new_challenger|challenger) == CH_(\w+):\n\s+yuramon\.say\(t\("(\w+)\.rumour\.who"\), t\("\3\.rumour\.where"\)\)', talk)
        want = {('new_challenger' if r['pool'] == 'new' else 'challenger', r['name'].upper(), r['name'].lower())
                for r in self.rows if r.get('hint')}
        self.assertEqual(sorted(set(told)), sorted(want))
        self.assertEqual(len(told), len(want))
        self.assertTrue(all(isinstance(r.get('hint', False), bool) for r in self.rows))
        keys = {f'{n}.rumour.{w}' for _, _, n in want for w in ('who', 'where')} | {'rumour.unheard', 'rumour.quiet'}
        for lang in ('en',) + LANGS:
            bank = json.loads((MOD / f'text/{lang}.json').read_text())
            self.assertEqual(sorted(keys - set(bank)), [], lang)

    def test_every_stage_has_challengers(self):
        """Stage rule same-or-lower: a Rookie partner and up always has a few residents who can go out."""
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
        levels = [city.LEVELS[species[r['species']]['level']] for r in self.rows]
        for stage in ('rookie', 'champion', 'ultimate', 'mega'):
            self.assertGreaterEqual(sum(lv <= city.LEVELS[stage] for lv in levels), 3, stage)


if __name__ == '__main__':
    unittest.main()
