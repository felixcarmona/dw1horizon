"""Runtime language transitions and translation-bank integrity (no emulator needed)."""
import json
import hashlib
import pathlib
import re
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.languages import selected, translations
from tools.langpatch import all_language_runs, write_patch
from tools.localize.executable.padding import merge


def flat(value):
    return value if isinstance(value, str) else ' '.join(flat(v) for v in value)


class Languages(unittest.TestCase):
    def test_no_spanish_draft_words_in_translations(self):
        from tools.localize.audit import audit
        self.assertEqual(list(audit()), [])

    def test_spanish_leak_check_covers_case_pages_and_japanese_boundaries(self):
        from tools.localize.audit import spanish_leaks
        for lang in ('pt-br', 'fr', 'de', 'it', 'ja'):
            for value in ('Jugar EN RANURA 1', [['borrar partida']], 'RANURAのデータ', 'MODO FUNK'):
                with self.subTest(lang=lang, value=value):
                    self.assertTrue(spanish_leaks(value, lang))
        for lang, value in (('ca', 'Esborrar partida, ranura 1'),
                            ('pt-br', 'Eu devo guardar este lugar.'),
                            ('it', "Non c'è altro modo."),
                            ('fr', '{item ranura}')):
            self.assertEqual(spanish_leaks(value, lang), [])

    def test_title_menu_uses_console_ui_terms_and_fits_the_text_area(self):
        from tools.fontgen import text_width
        from tools.localize.executable.bank import list_width
        expected = {
            'pt-br': ('NOVO JOGO', 'CONTINUAR', 'APAGAR JOGO', 'BATALHA DE CARTAS'),
            'fr': ('NOUVELLE PARTIE', 'CONTINUER', 'EFFACER', 'COMBAT DE CARTES'),
            'de': ('NEUES SPIEL', 'FORTSETZEN', 'SPIEL LÖSCHEN', 'KARTENKAMPF'),
            'it': ('NUOVA PARTITA', 'CONTINUA', 'CANCELLA', 'BATTAGLIA DI CARTE'),
            'ja': ('はじめから', 'つづきから', 'データ削除', 'カードバトル'),
            'ca': ('PARTIDA NOVA', 'CONTINUAR', 'ESBORRAR PARTIDA', 'COMBAT DE CARTES'),
        }
        for lang, labels in expected.items():
            names = json.loads((ROOT / f'text/{lang}/names.json').read_text())
            for suffix, label in zip(('31008', '31014', '31024', '31030'), labels):
                self.assertEqual(names['main.MAIN_D_801' + suffix], label, lang)
            for key, value in names.items():
                if key.startswith('main.MAIN_D_80131'):
                    for font in ('original', 'b'):
                        self.assertLessEqual(text_width(value, font), 244, (lang, key, font))
            for suffix in ('31008', '31014', '31024', '31030'):
                value = names['main.MAIN_D_801' + suffix]
                self.assertLessEqual(text_width(value, 'b'), 164, (lang, suffix))
                # The original-font title renderer uses fitStringMode, just as
                # the item/species lists do, leaving 12 pixels in its 176-pixel crop.
                self.assertLessEqual(list_width(value, 'original'), 164, (lang, suffix))
            for suffix in ('3103C', '3104C', '3105C', '3106C'):
                for font in ('original', 'b'):
                    self.assertLessEqual(text_width(names['main.MAIN_D_801' + suffix], font),
                                         190, (lang, suffix, font))

    def test_playable_strings_use_supported_japanese_glyphs(self):
        from tools.localize.audit import LANGUAGES, banks, strings
        from tools.dws.backend import EXTRA_ORDER
        from tools.dws.textbank import CJK
        available = set(EXTRA_ORDER)
        for lang in LANGUAGES:
            for path in banks(lang):
                for key, value in json.loads(path.read_text()).items():
                    if key.startswith('_'):
                        continue
                    for text in strings(value):
                        self.assertEqual(set(CJK.findall(text)) - available, set(),
                                         (lang, path.name, key))

    def test_executable_translations_fit_the_font_and_embedded_records(self):
        from tools.localize.audit import LANGUAGES
        from tools.localize.executable.bank import exe_bank
        for lang in LANGUAGES:
            for font in ('original', 'b'):
                _, kept = exe_bank(lang, exe_font=font)
                self.assertEqual(kept, [], (lang, font))

    def test_item_effect_descriptions_fit_the_inventory_single_row(self):
        from tools.fontgen import text_width
        from tools.localize.audit import LANGUAGES
        for lang in LANGUAGES:
            names = json.loads((ROOT / f'text/{lang}/names.json').read_text())
            for key, value in names.items():
                if key.startswith('main.ITEM_DESCS.'):
                    for font in ('original', 'b'):
                        self.assertLessEqual(text_width(value, font), 244, (lang, key, font))

    def test_translated_choices_fit_the_script_menu_row(self):
        from tools.localize.audit import LANGUAGES, banks
        from tools.dws import backend as be
        previous = dict(be.FONT)
        try:
            for font in ('original', 'b'):
                be.FONT.update(extra=True, glyphs=len(be.EXTRA_ORDER),
                               chars=frozenset(be.EXTRA_ORDER), name=font)
                for lang in LANGUAGES:
                    for path in banks(lang):
                        if 'dialogue' not in path.parts:
                            continue
                        for key, value in json.loads(path.read_text()).items():
                            if re.search(r'\.m\d+\.o\d+$', key) and isinstance(value, str):
                                self.assertTrue(be.fits(value, packed=be.packed_key(key)),
                                                (lang, path.name, key, font, value))
        finally:
            be.FONT.clear()
            be.FONT.update(previous)

    def test_supported_subsets_and_boot_language(self):
        self.assertEqual(selected({'LANGS': 'pt-br,en,es', 'LANG_BASE': 'pt-br'}), ('en', 'es', 'pt-br'))
        self.assertEqual(translations({'LANGS': 'en,pt-br'}), ('pt-br',))
        self.assertEqual(selected({}), ())
        self.assertEqual(selected({'LANGS': 'ja,it,de,fr,pt-br,es,en'}), ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja'))
        for env in ({'LANGS': 'en,xx'}, {'LANGS': 'en,es,es'}, {'LANGS': 'es,pt-br'},
                    {'LANGS': 'en,pt-br', 'LANG_BASE': 'es'}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                selected(env)

    def test_every_transition_restores_bytes_shared_by_only_two_languages(self):
        images = [b'Original text!\x00\x00', b'Outro texto!!!\x00\x00', b'Original TEXt!\x00\x00']
        self.assertEqual(len({len(v) for v in images}), 1)
        targets = all_language_runs(images, 0x80010000, gap=0)
        with tempfile.TemporaryDirectory() as tmp:
            for target, spans in zip(images, targets):
                path = pathlib.Path(tmp) / 'LANG.BIN'
                write_patch(spans, path)
                patch = path.read_bytes()
                count, = struct.unpack_from('<I', patch, 4)
                for source in images:
                    ram = bytearray(source)
                    off = 8
                    for _ in range(count):
                        addr, size = struct.unpack_from('<II', patch, off)
                        off += 8
                        ram[addr - 0x80010000:addr - 0x80010000 + size] = patch[off:off + size]
                        off += size + (-size % 4)
                    self.assertEqual(bytes(ram), target)

    def test_all_eight_language_transitions(self):
        images = [bytes((i if j % 8 == i else j % 3) for j in range(64)) for i in range(8)]
        patches = all_language_runs(images, 0x80010000, gap=0)
        for source in images:
            for target, spans in zip(images, patches):
                ram = bytearray(source)
                for address, data in spans:
                    offset = address - 0x80010000
                    ram[offset:offset + len(data)] = data
                self.assertEqual(bytes(ram), target)

    def test_original_font_width_uses_committed_metrics_without_a_disc(self):
        from tools import fontgen
        from unittest import mock
        with mock.patch.object(fontgen, 'base_font', side_effect=AssertionError('disc bitmap read')):
            self.assertEqual(fontgen.text_width('AB C', 'original'), 44)

    def test_japanese_private_use_codes_span_multiple_leads(self):
        from tools import fontgen
        for index in (0, 62, 63, 70, 187, 188, 376, 1879):
            code = fontgen.index_to_code(index)
            self.assertEqual(fontgen.code_to_index(code), index)
            self.assertNotEqual(code & 255, 127)
        self.assertEqual(fontgen.index_to_code(0), 0xF040)
        self.assertEqual(fontgen.index_to_code(188), 0xF140)

    def test_japanese_wraps_without_inventing_spaces_or_splitting_references(self):
        from tools.dws import backend as be
        previous = dict(be.FONT)
        try:
            be.FONT.update(extra=True, glyphs=len(be.EXTRA_ORDER), chars=frozenset(be.EXTRA_ORDER), name='b')
            text = 'あいうえお' * 12 + '{player}' + 'かきくけこ' * 12
            pages = be.wrap(text, 4)
            rows = [row for page in pages for row in page]
            self.assertEqual(''.join(rows), text)
            self.assertTrue(all(be.fits(row) for row in rows))
            self.assertEqual(sum('{player}' in row for row in rows), 1)
        finally:
            be.FONT.clear()
            be.FONT.update(previous)

    def test_padding_measures_encoded_accents_and_keeps_distinct_keys(self):
        font = {'ã': 'F040'}
        banks = [{'font': font, 'text': {'a': 'yes', 'b': 'yes'}},
                 {'font': font, 'text': {'a': 'sim', 'b': 'sim'}},
                 {'font': font, 'text': {'a': 'não', 'b': 'ããã'}}]
        pad = merge(banks)
        self.assertTrue(pad['identity'])
        self.assertEqual(pad['text']['b'], 'ããã')
        self.assertEqual(set(pad['text']), {'a', 'b'})

    def test_padding_aliases_require_agreement_in_every_language(self):
        banks = [{'font': {}, 'text': {'a': 'yes', 'b': 'yes', 'c': 'yes', 'd': 'yes'}},
                 {'font': {}, 'text': {'a': 'oui', 'b': 'oui', 'c': 'non'}}]
        aliases = merge(banks)['aliases']
        self.assertEqual(aliases['a'], aliases['b'])
        self.assertNotEqual(aliases['a'], aliases['c'])
        self.assertNotIn('d', aliases)

    def test_japanese_dictionary_roundtrips_every_pixel(self):
        from tools import fontgen
        glyphs = fontgen.load_extra()[len(fontgen.load_extra(include_japanese=False)):]
        words, data = fontgen.japanese_dictionary(glyphs)
        self.assertLessEqual(len(words), 512)
        for index, (char, width, rows) in enumerate(glyphs):
            for row in range(10):
                bit = index * 90 + row * 9
                pair = (data[bit >> 3] << 8) | data[(bit >> 3) + 1]
                decoded = words[(pair >> (7 - (bit & 7))) & 511]
                self.assertEqual(decoded, fontgen.row_word(rows[row]), (char, row))

    def test_huffman_font_preserves_every_row_and_random_access_boundary(self):
        from tools import fontgen
        glyphs = fontgen.load_extra()[71:]
        words, counts, offsets, bits = fontgen.japanese_huffman(glyphs)
        for glyph in range(len(glyphs)):
            bit = offsets[glyph // 8]
            rows = []
            for _ in range((glyph % 8 + 1) * 10):
                code = first = index = 0
                for length in range(1, len(counts)):
                    code = (code << 1) | ((bits[bit >> 3] >> (7 - (bit & 7))) & 1)
                    bit += 1
                    if code - first < counts[length]:
                        rows.append(words[index + code - first])
                        break
                    index += counts[length]
                    first = (first + counts[length]) << 1
            self.assertEqual(rows[-10:], [fontgen.row_word(row) for row in glyphs[glyph][2][:10]])

    def test_hashed_sector_table_preserves_names_and_relocation(self):
        from tools import isowriter
        names = ('DG.SCN', 'LJ001.SCN', '_J001.SCN', 'LANGCA.BIN')
        data = bytearray(struct.pack('<III', 0x48465744, 0x00010001, 0))
        for name in names:
            data.extend(struct.pack('<iiI', 0, 2048, isowriter.filename_hash(name)))
        data.extend(bytes(12))
        where = {name: (100 + i, 3000 + i) for i, name in enumerate(names)}
        count, changed, missing, found = isowriter.rewrite_file_table(data, 0, where)
        self.assertEqual((count, changed, missing, found), (4, 4, [], set(names)))
        entries = isowriter.file_table_entries(data, 0, names=where)
        self.assertEqual({name:(sector,size) for _,sector,size,name in entries},where)
        self.assertEqual(struct.unpack_from('<III',data), (0x48465744,0x00010001,0))

    def test_new_languages_cover_spanish_and_preserve_runtime_references(self):
        sources = list((ROOT / 'text/es/dialogue').glob('*.json'))
        sources += [ROOT / 'text/es.json']
        sources += list((ROOT / 'story/mods').glob('*/text/es.json'))
        refs = lambda value: set(re.findall(r'\{(?!color\b)[^{}]+\}', flat(value)))
        for lang in ('fr', 'de', 'it', 'ja', 'ca'):
            for source in sources:
                target = pathlib.Path(str(source).replace('/text/es/', f'/text/{lang}/').replace('/text/es.json', f'/text/{lang}.json'))
                original = json.loads(source.read_text())
                translated = json.loads(target.read_text())
                keys = {key for key in original if not key.startswith('_')}
                self.assertEqual(keys, {key for key in translated if not key.startswith('_')}, str(target))
                for key in keys:
                    self.assertEqual(refs(original[key]), refs(translated[key]), (lang, source.name, key))
                    self.assertNotRegex(flat(translated[key]), r'QZX\d+XZQ|▁', (lang, key))
            names = json.loads((ROOT / f'text/{lang}/names.json').read_text())
            self.assertTrue(all(isinstance(value, str) for key, value in names.items() if not key.startswith('_')))

    def test_new_language_option_rows_fit_the_original_viewport(self):
        from tools import fontgen
        labels = ('JP', 'CLOCK', 'BARS', 'EVO', 'NEWDIGI', 'STORY', 'FPS', 'FONT', 'LANG', 'SIGNS')
        values = ('OFF', 'ON', '20', '60', 'NEW', 'CLASSIC', 'ORIGINAL', 'TRANSLATED',
                  'ENGLISH', 'SPANISH', 'PORTUGUESE', 'FRENCH', 'GERMAN', 'ITALIAN', 'JAPANESE')
        for lang in ('fr', 'de', 'it', 'ja', 'ca'):
            names = json.loads((ROOT / f'text/{lang}/names.json').read_text())
            width = lambda key: fontgen.text_width(names['main.MOD_OPT_STR_' + key], 'original') + 1
            # drawOptionsText measures the widest label and value, adds an eight
            # pixel gap and two eight-pixel frame margins, in a 304-pixel area.
            total = max(map(width, labels)) + 8 + max(map(width, values)) + 16
            self.assertLessEqual(total, 304, lang)

    def test_disc_copies_share_one_row_without_overwriting_other_languages(self):
        from tools.derive.steps.plan import Plan
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, 'lang').mkdir()
            ctx = SimpleNamespace(path=lambda *p: str(pathlib.Path(tmp, *p)))
            plan = Plan(ctx)
            es = plan.lang_copy('DG.SCN', 'SCN', data=b'es')
            pt = plan.lang_copy('DG.SCN', 'SCN', data=b'pt', lang='pt-br')
            self.assertEqual(plan.lang_files, [f'DG.SCN:{es}:-:{pt}'])
            self.assertNotEqual(es, pt)
            self.assertEqual(plan.lang_of('DG.SCN', 1), es)
            self.assertEqual(plan.lang_of('DG.SCN', 3), pt)

    def test_portuguese_without_spanish_still_builds_its_story_pass(self):
        from tools.derive.steps.story import Settings
        from types import SimpleNamespace
        ctx = SimpleNamespace(env={'TEXT': 'ours', 'LANGS': 'en,pt-br'}, facts={}, out='/tmp/story',
                              path=lambda *p: str(pathlib.Path('/tmp/story', *p)))
        settings = Settings(ctx)
        self.assertTrue(settings.lang_on)
        self.assertEqual([p[0] for p in settings.langs(ctx)], ['en', 'pt-br'])
        self.assertEqual(settings.langs(ctx)[1][2:4], ('pt-br', 'pt-br'))

    def test_all_portuguese_dialogue_keys_and_runtime_references_exist(self):
        for source in (ROOT / 'text/ours/dialogue').glob('*.json'):
            original = json.loads(source.read_text())
            translated = json.loads((ROOT / 'text/pt-br/dialogue' / source.name).read_text())
            keys = {k for k in original if not k.startswith('_')}
            self.assertEqual(keys, {k for k in translated if not k.startswith('_')}, source.name)
            for key in keys:
                # Colour/name headings can repeat on newly wrapped pages. Runtime references
                # must still be present; no new item, variable or player reference may appear.
                refs = lambda s: set(re.findall(r'\{(?!color\b)[^{}]+\}', flat(s)))
                self.assertEqual(refs(original[key]), refs(translated[key]), key)
                self.assertNotRegex(flat(translated[key]), r'QZX\d+XZQ|▁', key)


if __name__ == '__main__':
    unittest.main()
