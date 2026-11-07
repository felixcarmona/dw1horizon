"""Recruit coverage, script evidence and localized snapshot regressions."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as guide
import recruits


class RecruitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit, _, cls.species, _, cls.files = guide.snapshot('v0.0.7')
        cls.rows = recruits.load(cls.files, cls.species)
        cls.by_id = {r['id']: r for r in cls.rows}

    def test_exact_roster_and_city_prosperity(self):
        roster = json.loads(self.files['content/tables/city-residents.json'])
        self.assertEqual({r['id'] for r in roster}, self.by_id.keys())
        self.assertEqual(len(self.rows), 72)
        self.assertEqual(sum(r['points'] for r in self.rows), 144)
        self.assertEqual(sum(r['points'] for r in self.rows if r['id'] < 59), 101)
        for ident in (11, 39, 53):
            self.assertEqual(self.by_id[ident]['points'], 1)
        self.assertNotIn(109, self.by_id)  # Otamamon is story state, not a resident.
        for row in self.rows:
            self.assertTrue(row['evidence'], row['name'])

    def test_ten_script_checked_entries(self):
        # Each case names a source operation whose player meaning was reviewed.
        cases = {
            5: (4800, 'Prosperity 15', 'engine.prosperity >= 15'),
            19: (None, 'Greymon first', 'if not recruited(Species.Greymon):'),
            22: (4200, '15:00–23:59', 'garurumon_promise_days == 1'),
            25: (None, 'day 15', 'if date_day != 14:'),
            38: (None, 'three game days', 'drimogemon_job_days >= 3'),
            47: (None, '20 customers', 'meat_stand.customers >= 20'),
            229: (1500, '20:00–23:59', 'clock.hour >= 20'),
            273: (None, 'Any time', 'take(Item.SweetNut)'),
            290: (None, '14:00–23:59', 'clock.hour >= 11 and clock.hour <= 13'),
            351: (1200, 'Fortress is cleared', 'when=ogre_fortress_cleared and not recruited'),
        }
        for ident, (hp, words, operation) in cases.items():
            with self.subTest(ident=ident):
                row = self.by_id[ident]
                self.assertEqual(row['hp'], hp)
                self.assertIn(words, row['when'])
                self.assertTrue(any(operation in self.files[p].decode() for p in row['evidence']))

    def test_map_hp_uses_deltas_and_snapshot_content(self):
        self.assertEqual(self.by_id[22]['rematch_hp'], 2100)
        self.assertEqual(self.by_id[3]['hp'], 400)
        self.assertEqual(self.by_id[9]['hp'], 2600)
        files = dict(self.files)
        path = 'content/maps/TUNN08.json'
        value = json.loads(files[path])
        value['digimon'][0]['hp'] = '+2500'
        files[path] = json.dumps(value).encode()
        result = {r['id']: r for r in recruits.load(files, self.species)}
        self.assertEqual(result[9]['hp'], 3000)
        self.assertEqual(self.by_id[9]['hp'], 2600)

    def test_changed_quest_assertions_fail_loudly(self):
        files = dict(self.files)
        path = 'story/mods/what-the-island-forgot/arcs/residents/clockmon.py'
        files[path] = files[path].replace(b'clock.hour <= 13', b'clock.hour <= 14')
        with self.assertRaisesRegex(ValueError, 'Review recruit 290'):
            recruits.load(files, self.species)

    def test_all_nine_languages_have_every_recruit_field(self):
        for path in (guide.ROOT / 'web/i18n').glob('*.json'):
            lang = path.stem
            strings = json.loads(path.read_text())
            page = guide.render_recruits(self.rows, self.files, lang, strings)
            self.assertEqual(page.count('<tr id="recruit-'), 72)
            self.assertIn(strings['data.recruit.title'], page)
            self.assertIn(strings['data.recruit.search'], page)
            self.assertIn(strings['data.recruit.table'], page)
            for row in self.rows:
                self.assertIn(strings[f'data.recruit.method.{row["id"]}'], page)
                if lang == 'en':
                    self.assertEqual(strings[f'data.recruit.method.{row["id"]}'], row['method'])
                    self.assertEqual(strings[f'data.recruit.when.{row["id"]}'], row['when'])
            self.assertNotIn('Search ', page if lang != 'en' else '')

    def test_names_follow_runtime_and_places_follow_game_terms(self):
        self.assertEqual(recruits.species_name(self.files, 'Agumon', 'zh-hans'), '亚古兽')
        self.assertEqual(recruits.species_name(self.files, 'Agumon', 'ja'), 'Agumon')
        for lang in ('es', 'ja', 'zh-hans'):
            terms = json.loads(self.files[f'text/{lang}/places.json'])['places']
            self.assertEqual(recruits.screen_name(self.files, 1, lang), terms['KUNEMONS_BED']['name'])
            self.assertEqual(recruits.screen_name(self.files, 254, lang), terms['MT_INFINITY']['name'])
            self.assertEqual(recruits.screen_name(self.files, 25, lang), terms['DRILL_TUNNEL_2ND_FLOOR']['name'])


if __name__ == '__main__':
    unittest.main()
