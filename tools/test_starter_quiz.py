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
from languages import CODES


class QuizTest(unittest.TestCase):
    def test_starter_stays_hidden_in_every_language(self):
        Q.check_reveal_text()
        bank_path = Q.ROOT / 'text/en.json'
        original = Path.read_text
        for key in ('name.quiz.result', 'name.confirm_partner'):
            for spoiler in ('{partner}', '{digimon 254}', 'Agumon'):
                with self.subTest(key=key, spoiler=spoiler):
                    def read(path, *args, **kwargs):
                        if path == bank_path:
                            bank = json.loads(original(path))
                            bank[key][1] = spoiler
                            return json.dumps(bank)
                        return original(path, *args, **kwargs)
                    with patch.object(Path, 'read_text', read), self.assertRaises(ValueError):
                        Q.check_reveal_text()

    def test_distribution(self):
        self.assertEqual(sum(Q.check(Q.load()).values()), 2187)

    def test_changed_cells_and_original_fallback(self):
        data = Q.load()
        self.assertEqual([data['starters'][data['quiz']['cells'][i]] for i in (33, 34, 35, 26, 24)],
                         [263, 183, 74, 283, 4])
        self.assertNotIn(32, {data['starters'][i] for i in data['quiz']['cells']})
        self.assertIn(32, {data['starters'][i] for i in data['quiz']['vanillaCells']})
        # Preserve the original-game grid and the original list indices.
        self.assertEqual(data['quiz']['vanillaCells'], [
            3, 1, 4, 3, 1, 4, 1, 4, 4, 0, 0, 0, 1, 0, 1, 0, 0, 6,
            8, 2, 7, 8, 8, 8, 2, 2, 2, 7, 7, 7, 7, 5, 8, 5, 5, 5,
            6, 6, 6, 3, 3, 3, 6, 6, 3])

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

    def test_opening_techniques_match_evolution(self):
        # A quiz starter opens with what evolving into it teaches; Agumon's and Gabumon's authored rows are that too.
        # No starter opens with more than a native Rookie learns on evolving (Betamon's Winter Blast, 120), or than the
        # weakest technique of its element (mech: Metal Sprinter, 150).
        import species as S
        records = S.load_content()
        techs = {int(t['id']): t for t in (json.loads(p.read_text()) for p in (Q.ROOT / 'content/techniques').glob('*.json'))}
        powers = {i: t['power'] for i, t in techs.items()}
        disc = json.loads((Q.ROOT / 'content/tables/disc-species.json').read_text())['species']
        native = [Q.opening_technique(r['para'], powers) for r in disc if r['raise'] and r['para']['level'] == 3]
        ceiling = max(powers[t] for t, _ in native)
        for starter in Q.load()['starters']:
            s = records[starter]
            para = S.species_record(s)['para']
            tech, slot = Q.opening_technique(para, powers)
            with self.subTest(starter=s['name']):
                self.assertLess(tech, 58)
                self.assertEqual(para['moves'][slot], tech)
                weakest = min(t['power'] for i, t in techs.items() if i < 58 and t['power'] and t['element'] == techs[tech]['element'])
                self.assertLessEqual(powers[tech], max(ceiling, weakest), techs[tech]['name'])
                if 'new_game_technique' in s:
                    self.assertEqual(techs[tech]['name'], s['new_game_technique'])
        gotsumon = Q.opening_technique(S.species_record(records[68])['para'], powers)
        self.assertEqual(techs[gotsumon[0]]['name'], 'Sonic Jab')

    def test_text_table_keeps_legacy_entries(self):
        legacy = (Q.ROOT / 'story/base/maphead/global-1238.dws').read_text()
        expanded = (Q.ROOT / 'story/new-game-quiz.dws').read_text()
        pattern = r'show_textbox\(text\("([^"]+)"\)\)'
        old = re.findall(pattern, legacy)
        new = re.findall(pattern, expanded)
        self.assertEqual(len(old), 35)
        old[30] = 'name.confirm_partner'  # same entry, without echoing the hidden default
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
        for lang in CODES:
            bank = json.loads((Q.ROOT / 'text' / (lang + '.json')).read_text())
            for key, rows in bank.items():
                if key.startswith('name.quiz.') and key.endswith('.answers'):
                    self.assertTrue(all(len(row) <= 21 for row in rows[1:]), (lang, key))

    def test_translated_boxes(self):
        from dws.text import layout
        species = [json.loads(p.read_text()) for p in (Q.ROOT / 'content/species').glob('*.json')]
        names = [s['name'] for s in species if s['id'] in Q.load()['starters']]
        for lang in CODES:
            bank = json.loads((Q.ROOT / 'text' / (lang + '.json')).read_text())
            lines = {k: v for k, v in bank.items()
                     if k.startswith('name.quiz.') or k == 'name.confirm_partner'}
            self.assertEqual(len(lines), 24, lang)
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
        source = next((Q.ROOT / f'build/{tree}/src/main/main_menu.c'
                       for tree in ('decomp-dev', 'decomp-int')
                       if (Q.ROOT / f'build/{tree}/src/main/main_menu.c').exists()),
                      Q.ROOT / 'build/decomp-dev/src/main/main_menu.c')
        if not source.exists() or not shutil.which('cc'):
            self.skipTest('needs a prepared decomp tree and a host C compiler')
        text = source.read_text()
        found = re.search(r'uint8_t modQuizResult\(const uint8_t \*answers\)\n\{.*?\n\}', text, re.S)
        if found is None:
            self.skipTest('prepared decomp tree does not include the quiz patch')
        data = Q.load()
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'quiz.c'
            so = Path(tmp) / 'quiz.so'
            header = (source.parents[2] / 'include/dw/mod_rules.h').read_text()
            defines = '\n'.join(line for line in header.splitlines()
                                if line.startswith(('#define MOD_NEWGAME_SIZE', '#define MOD_QUIZ_')))
            starter = re.search(r'int32_t modNewGameStarter\(void\)\n\{.*?\n\}', text, re.S)[0]
            c.write_text('#include <stdint.h>\nint32_t MOD_OPT_NEW_DIGIMON = 1;\n' + defines + '\n'
                         'int32_t MOD_NEWGAME[MOD_NEWGAME_SIZE];\n'
                         'uint32_t test_index;\n#define PSTAT_254 254\n'
                         'uint32_t readPStat(int n) { (void)n; return test_index; }\n' + starter + '\n' + found[0])
            subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-O2', c, '-o', so], check=True)
            lib = ctypes.CDLL(str(so))
            table = (ctypes.c_uint8 * (80 + Q.SIZE)).in_dll(lib, 'MOD_NEWGAME')
            table[80:] = Q.pack(data)
            index = ctypes.c_uint32.in_dll(lib, 'test_index')
            for index.value in range(256):
                self.assertEqual(lib.modNewGameStarter(), data['starters'][index.value if index.value < Q.COUNT else 0])
            fn = lib.modQuizResult
            option = ctypes.c_int32.in_dll(lib, 'MOD_OPT_NEW_DIGIMON')
            fn.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
            fn.restype = ctypes.c_uint8
            for option.value in (1, 0):
                for path in itertools.product(range(3), repeat=7):
                    self.assertEqual(fn((ctypes.c_uint8*7)(*path)), Q.result(data, path, option.value != 0), path)

    def test_production_naming_flow_keeps_default_private(self):
        source = next((Q.ROOT / f'build/{tree}/src/shop/script_menu.c'
                       for tree in ('decomp-int', 'decomp-dev')
                       if (Q.ROOT / f'build/{tree}/src/shop/script_menu.c').exists()), None)
        if source is None or not shutil.which('cc'):
            self.skipTest('needs a prepared decomp tree and a host C compiler')
        function = re.search(r'int32_t newGameStateMachine\(void\)\n\{.*?\n\}',
                             source.read_text(), re.S)[0]
        # Run the actual state machine; replace only UI/engine boundaries.
        stubs = r'''
#include <stdint.h>
#include <string.h>
#define VERSION_IS(x) 1
#define TRIGGER_49 49
#define PSTAT_254 254
#define DIGIMON_NAME(x) player
int SCRIPT_STATE_2, SCRIPT_NEXT_STATE_2, SCRIPT_TEXTBOX_MODE;
int NAMING_BOX_FLAG, DRAW_STRING2_IS_FIXED_WIDTH, entry = -1, species_calls;
char NAMING_BUFFER[32], player[32];
struct { struct { struct { int type; } entity; } digimonEntity; char name[32]; } PARTNER_ENTITY;
struct { int state; } UI_BOX_DATA[3];
void setTrigger(int n) { (void)n; }
void unsetTrigger(int n) { (void)n; }
void closeBox(int n) { (void)n; }
void triggerBoxCloseFlag(int n) { (void)n; }
void setInputRepeatMask(int n) { (void)n; }
void setupNewGameDialogueBox(void) {}
void setupNameSelectorBox(void) {}
void setupNameDisplayBox(void) {}
void writePStat(int n, int v) { (void)n; (void)v; }
int modNewGameStarter(void) { return 263; }
uint8_t modQuizResult(const uint8_t *answers) { (void)answers; return 12; }
void modPartnerNameSetSpecies(int n) {
    (void)n; species_calls++; strcpy(PARTNER_ENTITY.name, "Mushroomon");
}
void showNewGameDialogue(int e, int next) {
    entry = e; SCRIPT_STATE_2 = 1; SCRIPT_NEXT_STATE_2 = next;
}
void showNewGameSelection(int e, int next) { showNewGameDialogue(e, next); }
void showMapheadSelection(int e, int owner, int count, int *sel, int section) {
    (void)owner; (void)count; (void)sel; (void)section; entry = e;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c, so = Path(tmp) / 'naming.c', Path(tmp) / 'naming.so'
            c.write_text(stubs + function)
            subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-O2',
                            c, '-o', so], check=True)
            lib = ctypes.CDLL(str(so))
            def var(name): return ctypes.c_int.in_dll(lib, name)
            state, flags, entry = (var(n) for n in ('SCRIPT_STATE_2', 'NAMING_BOX_FLAG', 'entry'))
            buffer = (ctypes.c_char * 32).in_dll(lib, 'NAMING_BUFFER')
            def step(n):
                state.value, entry.value = n, -1
                return lib.newGameStateMachine()
            # All seven answers precede the neutral result; no species name is prepared for it.
            step(2)
            for _ in range(7):
                step(0x23); step(0x24); step(0x25); step(0x26)
            step(0x23)
            self.assertEqual(entry.value, 0x39)
            self.assertEqual(var('species_calls').value, 0)
            flags.value = 0
            buffer.value = b'A'
            step(0x15); step(0x16)
            self.assertEqual(entry.value, 0x1b)  # tamer still confirms
            step(0x18); step(0x20); step(0x21); step(0x1a)
            self.assertEqual(buffer.value, b'')  # partner keyboard never prefills a species
            step(0x15); step(0x16)
            self.assertEqual(var('species_calls').value, 1)
            self.assertEqual(entry.value, 0x1e)  # neutral confirmation never interpolates the default
            self.assertEqual(var('SCRIPT_NEXT_STATE_2').value, 0x1b)
            step(0x1c)
            step(0x1e)
            self.assertEqual(entry.value, 0x20)  # farewell, then movie
            # A typed name keeps its confirmation and No returns to its keyboard.
            buffer.value = b'Buddy'
            step(0x15); step(0x16)
            self.assertEqual(entry.value, 0x1e)
            self.assertEqual(var('SCRIPT_NEXT_STATE_2').value, 0x1b)
            step(0x1d)
            self.assertEqual(state.value, 0x13)
            self.assertEqual(buffer.value, b'Buddy')
            step(0x22)  # choosing not to name also bypasses confirmation
            self.assertEqual(state.value, 0x1e)
            flags.value = 3  # renaming after meeting the partner remains unchanged
            self.assertEqual(step(0x16), 1)


if __name__ == '__main__':
    unittest.main()
