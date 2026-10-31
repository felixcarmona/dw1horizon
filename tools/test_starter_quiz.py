#!/usr/bin/env python3
"""Quiz validation, packed table and production C/Python agreement."""
import copy
import ctypes
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import starter_quiz as Q


class QuizTest(unittest.TestCase):
    def test_distribution(self):
        self.assertEqual(sum(Q.check(Q.load()).values()), 2187)

    def test_invalid_data(self):
        for change in ('pool', 'cell', 'weight', 'axis', 'question', 'fixed', 'vanilla'):
            with self.subTest(change=change):
                data = copy.deepcopy(Q.load())
                if change == 'pool': data['starters'][-1] = data['starters'][0]
                if change == 'cell': data['quiz']['cells'][0] = Q.COUNT
                if change == 'weight': data['quiz']['weights'][0][0]['bold'] = 16
                if change == 'axis': data['quiz']['weights'][0][0] = {'unknown': 1}
                if change == 'question': data['quiz']['weights'].pop()
                if change == 'fixed': data['quiz']['cells'][9] = 1
                if change == 'vanilla': data['quiz']['vanillaCells'][0] = data['starters'].index(433)
                with self.assertRaises(ValueError): Q.validate(data)

    def test_latest_answer_and_same_answer_ties(self):
        data = Q.load()
        # Isolate each element in turn with the same score. Latest support wins;
        # if both receive their last point together, earlier axis order wins.
        data['quiz']['cells'] = list(range(45))
        data['quiz']['vanillaCells'] = list(range(45))
        data['quiz']['weights'] = [[{'vaccine': 1}]*3 for _ in range(7)]
        data['quiz']['weights'][0][0] = {'fire': 2}
        data['quiz']['weights'][6][0] = {'ice': 2}
        self.assertEqual(Q.result(data, [0]*7)//9, 2)
        data['quiz']['weights'][0][0] = {'fire': 1}
        data['quiz']['weights'][6][0] = {'fire': 1, 'ice': 2}
        self.assertEqual(Q.result(data, [0]*7)//9, 1)

    def test_balance_codec(self):
        import balance
        data = Q.load()
        class Exe:
            def where(self, key): return None, None, 80 + Q.SIZE
            def raw(self, key): return self.blob
        exe = Exe()
        exe.blob = balance.encode_named('newGame', data, exe)
        self.assertEqual(balance.decode_named('newGame', exe), data)

    def test_recolours_are_only_reached_by_evolution(self):
        for species, name in Q.RECOLOURS.items():
            self.assertNotIn(species, Q.load()['starters'], name)
        species = [json.loads(p.read_text()) for p in (Q.ROOT / 'content/species').glob('*.json')]
        names = {s['id']: s['name'] for s in species}
        self.assertTrue(all(names[i] == name for i, name in Q.RECOLOURS.items()))
        rookies = {s['id']: s for s in species}
        for i in Q.RECOLOURS:
            self.assertTrue(rookies[i].get('evolution', {}).get('from') or
                            rookies[i].get('evolution', {}).get('requirements', {}).get('digimon'), i)

    def test_every_partner_rookie_has_four_champions(self):
        species = [json.loads(p.read_text())
                   for p in (Q.ROOT / 'content/species').glob('*.json')]
        disc = json.loads((Q.ROOT / 'content/balance/engine/tables.json').read_text())['species']
        for rookie in (s['id'] for s in species if s.get('level') == 'rookie' and 'partner' in s):
            if rookie < 63 and str(rookie) in disc and 'to' in disc[str(rookie)].get('evoPaths', {}):
                continue  # the disc's own routes are counted from the built graph by tools/evo_graph.py
            # Count distinct published names, so an NPC duplicate cannot pad coverage.
            children = {s['name'] for s in species if s.get('level') == 'champion'
                        and 'partner' in s and rookie in
                        set(s.get('evolution', {}).get('from', []) +
                            [s.get('evolution', {}).get('requirements', {}).get('digimon')])}
            self.assertGreaterEqual(len(children), 4, rookie)

    def test_opening_techniques_are_learnable(self):
        import species as S
        records = S.load_content()
        for starter in Q.load()['starters']:
            record = S.species_record(records[starter])
            self.assertIn(record['para']['moves'][0], range(58), starter)

    def test_text_table_keeps_legacy_entries(self):
        legacy = (Q.ROOT / 'story/base/maphead/global-1238.dws').read_text()
        expanded = (Q.ROOT / 'story/new-game-quiz.dws').read_text()
        pattern = r'show_textbox\(text\("([^"]+)"\)\)'
        old = re.findall(pattern, legacy)
        new = re.findall(pattern, expanded)
        self.assertEqual(len(old), 35)
        self.assertEqual(new[:35], old)
        self.assertEqual(len(new), 58)
        self.assertEqual(new[35], 'name.quiz.intro')
        self.assertEqual(new[57], 'name.quiz.result')

    def test_actual_build_profile_includes_quiz_table(self):
        # The full driver uses --exe mods, not species. Compile a small real
        # base through the production story builder with that configuration.
        from dws import backend, basebuild, bytecode
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'base'
            (base / 'maphead').mkdir(parents=True)
            zone = base / 'zones' / 'test' / 's001'
            zone.mkdir(parents=True)
            (zone / 'script.dws').write_text('script 1 { on enter { } }')
            shutil.copy(Q.ROOT / 'story/base/maphead/global-1238.dws', base / 'maphead')
            for exe, capacity, expected in [('original', 25000, 35), ('mods', 32768, 58)]:
                with self.subTest(exe=exe), patch.object(backend, 'MAPHEAD_MAX_GIVEN', capacity), \
                     patch.object(backend, 'FONT_NAME_GIVEN', 'b'), \
                     patch.object(backend, 'FONT_GLYPHS_GIVEN', len(backend.EXTRA_ORDER)):
                    work = Path(tmp) / exe
                    work.mkdir()
                    _, archive = basebuild.compile_base_story(
                        str(base), str(work), 'en', [], {}, [], None, [],
                        from_py=False, text_source='us' if exe == 'original' else 'ours', exe=exe)
                    data = Path(archive).read_bytes()
                    _, sections, *_ = bytecode.sweep(data)
                    start = dict(sections)[1238]
                    jump = data[start:start + 2]
                    count = 0
                    while data[start + count * 4:start + count * 4 + 2] == jump:
                        count += 1
                    self.assertEqual(count, expected)

    def test_answers_fit_the_selection_bar(self):
        # The bar is sized from the longest answer; past 21 characters it overhangs the box.
        for lang in ('en', 'es', 'ca', 'de', 'fr', 'it', 'ja', 'pt-br'):
            bank = json.loads((Q.ROOT / 'text' / (lang + '.json')).read_text())
            for key, rows in bank.items():
                if key.startswith('name.quiz.') and key.endswith('.answers'):
                    self.assertTrue(all(len(row) <= 21 for row in rows[1:]), (lang, key))

    def test_translated_boxes(self):
        from dws.text import layout
        species = [json.loads(p.read_text()) for p in (Q.ROOT / 'content/species').glob('*.json')]
        names = [s['name'] for s in species if s['id'] in Q.load()['starters']]
        for lang in ('en', 'es', 'ca', 'de', 'fr', 'it', 'ja', 'pt-br'):
            bank = json.loads((Q.ROOT / 'text' / (lang + '.json')).read_text())
            lines = {k: v for k, v in bank.items() if k.startswith('name.quiz.')}
            self.assertEqual(len(lines), 23, lang)
            for fontname in ('b', 'original'):
                font = dict(name=fontname, extra=True)
                for key, rows in lines.items():
                    with self.subTest(lang=lang, font=fontname, key=key):
                        self.assertTrue(layout.fits(rows[0], font))
                        if key.endswith('.answers'):
                            self.assertEqual(len(rows), 4)
                            for i, row in enumerate(rows[1:]):
                                self.assertTrue(layout.fits(row, font, last_row=i == 2), row)
                        else:
                            for name in names if key.endswith('.result') else ['']:
                                text = ' '.join(rows[1:]).replace('{partner}', name)
                                self.assertEqual(len(layout.wrap(text, 3, font)), 1, text)
                                self.assertLessEqual(len(rows), 4)
                                for i, row in enumerate(rows[1:]):
                                    self.assertTrue(layout.fits(row.replace('{partner}', name), font,
                                                                last_row=i == 2), row)

    def test_production_c_all_paths(self):
        source = Q.ROOT / 'build/decomp-int/src/main/main_menu.c'
        if not source.exists() or not shutil.which('cc'):
            self.skipTest('needs prepared decomp-int and a host C compiler')
        text = source.read_text()
        found = re.search(r'uint8_t modQuizResult\(const uint8_t \*answers\)\n\{.*?\n\}', text, re.S)
        if found is None:
            self.skipTest('prepared decomp-int does not include the quiz patch')
        data = Q.load()
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'quiz.c'
            so = Path(tmp) / 'quiz.so'
            c.write_text('#include <stdint.h>\nint32_t MOD_OPT_NEW_DIGIMON = 1;\n'
                         'uint8_t table[' + str(Q.SIZE) + '] = {' +
                         ','.join(map(str, Q.pack(data))) + '};\n' +
                         f'#define MOD_QUIZ_WEIGHTS (table + {Q.WEIGHTS})\n' +
                         f'#define MOD_QUIZ_CELLS (table + {Q.CELLS})\n' +
                         f'#define MOD_QUIZ_VANILLA_CELLS (table + {Q.VANILLA_CELLS})\n' + found[0])
            subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-O2', c, '-o', so], check=True)
            lib = ctypes.CDLL(str(so))
            fn = lib.modQuizResult
            option = ctypes.c_int32.in_dll(lib, 'MOD_OPT_NEW_DIGIMON')
            fn.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
            fn.restype = ctypes.c_uint8
            for option.value in (1, 0):
                for path in itertools.product(range(3), repeat=7):
                    self.assertEqual(fn((ctypes.c_uint8*7)(*path)), Q.result(data, path, option.value != 0), path)


if __name__ == '__main__':
    unittest.main()
