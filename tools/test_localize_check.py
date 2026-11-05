"""Regression coverage for translation loss and actual renderer constraints."""
import unittest
from tools.localize.check import control_problems, custom_boxes, runtime_tokens


class LocalizationAudit(unittest.TestCase):
    def test_curling_options_keep_complete_words_in_their_rows(self):
        from tools.localize.check import curling_menu_problems, ROOT, LANGUAGES, FONTS
        from tools.localize.executable.chinese_layout import align
        import json
        key = 'kar.KAR_D_8005ABB8'
        for language in LANGUAGES:
            names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
            value = align(key, names[key]) if language == 'zh-hans' else names[key]
            for font in FONTS:
                self.assertEqual(curling_menu_problems(value, font, language), [], (language, font))
        self.assertTrue(curling_menu_problems('Começar Como Jogar', 'b', 'pt-br'))
        self.assertTrue(curling_menu_problems('Spielen          Regeln', 'original', 'de'))
        self.assertTrue(curling_menu_problems('Start          ' + 'W' * 8, 'original', 'en'))
        self.assertTrue(curling_menu_problems('Start          ' + 'x' * 30, 'b', 'en'))

    def test_place_names_check_aliases_source_mentions_and_row_breaks(self):
        from tools.localize.places import problems
        self.assertTrue(problems('pt-br', 'new', 'Lago Dragon Eye!'))
        self.assertFalse(problems('pt-br', 'new', [['Lago Olho de', 'Dragão!']]))
        self.assertTrue(problems('fr', 'new', 'Un autre nom.', 'Go to File City.'))
        self.assertFalse(problems('de', 'new', 'In der Großen Schlucht.', 'In Great Canyon.'))
        self.assertFalse(problems('ja', 'new', [['りゅうの目', 'の湖へ行こう。']], 'Go to Dragon Eye Lake.'))
        self.assertTrue(problems('ja', 'new', [['ドラゴン', 'アイ湖へ行こう。']]))
        self.assertTrue(problems('ja', 'new', 'Overdellに行こう。'))
        self.assertTrue(problems('zh-hans', 'new', '去Overdell吧。'))
        self.assertFalse(problems('fr', 'new', 'Le restaurant est ouvert.', 'The restaurant is open.'))
        self.assertFalse(problems('pt-br', 'new', 'A cidade cresceu.', 'The city grew.'))

    def test_place_glossaries_cover_all_captions_and_shared_locations(self):
        from tools.localize.places import catalog, EXTRA
        from tools.localize.check import LANGUAGES
        for language in LANGUAGES:
            if language == 'en':
                continue
            entries, english = catalog(language)
            self.assertEqual(entries.keys(), english.keys())
            self.assertTrue(EXTRA.keys() <= entries.keys())

    def test_inline_player_is_not_a_repeated_speaker(self):
        source = '{color 6}{player}{color 1}, thank you! I am joining the city.'
        value = [['{color 6}{player}{color 1}', 'Thanks!'],
                 ['{color 6}{player}{color 1}', 'I am joining the city.']]
        self.assertTrue(control_problems(source, value))
        self.assertFalse(control_problems(source, '{color 6}{player}{color 1}, merci!'))

    def test_speaker_may_repeat_but_may_not_change(self):
        source = ['{color 6}{player}{color 1}', 'Hello!']
        target = [['{color 6}{player}{color 1}.', 'Bonjour!'],
                  ['{color 6}{player}{color 1}', 'Merci!']]
        self.assertFalse(control_problems(source, target))
        target[1][0] = '{color 6}{partner}{color 1}'
        self.assertTrue(control_problems(source, target))

    def test_buttons_and_reference_order_are_preserved(self):
        self.assertTrue(control_problems('Press △ to skip.', 'Premi ∞.'))
        self.assertTrue(control_problems('{item 3} for {money}', '{money} for {item 3}'))
        self.assertTrue(control_problems('HP %d #C1', 'HP %s #C1', executable=True))
        self.assertFalse(control_problems('HP %d #C1', 'PV %d #C1', executable=True))

    def test_pager_does_not_promote_an_addressee_to_speaker(self):
        from tools.localize.review import wrap_page
        from dws import backend as be
        previous = dict(be.FONT)
        try:
            be.FONT.update(extra=True, chars=frozenset(be.EXTRA_ORDER), name='original')
            text = '{color 6}{player}{color 1}, ' + 'Thank you so much. ' * 8
            output = wrap_page([text], text)
            self.assertGreater(len(output), 1)
            self.assertEqual(sum(row.count('{player}') for page in output for row in page), 1)
            header = '{color 6}{player}{color 1}'
            output = wrap_page([header, 'Thank you so much. ' * 8], [header, 'Thanks.'])
            self.assertGreater(len(output), 1)
            self.assertTrue(all(page[0] == header for page in output))
        finally:
            be.FONT.clear()
            be.FONT.update(previous)

    def test_a_page_under_a_name_has_three_rows(self):
        from tools.dws.text.profiles import maphead_page_too_tall, tall_pages
        script = '\n'.join(['SET_DIALOG_OWNER 6', 'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "lost"', 'SET_DIALOG_OWNER 255',
                             'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "fits"', 'SET_DIALOG_OWNER 6', 'SET_TEXTBOX_SIZE 0, 20, 7',
                             'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "fits"', 'END_SECTION', 'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "?"'])
        self.assertEqual(tall_pages(script), [('6', ['a', 'b', 'c', 'lost'])])
        self.assertTrue(maphead_page_too_tall('m1230.u39', ['a', 'b', 'c', 'd']))
        self.assertFalse(maphead_page_too_tall('m1238.u16', ['{color 7}Jijimon {color 1}', 'b', 'c', 'd']))

    def test_named_keys_follow_the_owner_of_an_event(self):
        import pathlib, tempfile
        from tools.dws.text.profiles import named_keys, narrator_keys
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root, 'story/base/zones/z/s1/script.dws'); path.parent.mkdir(parents=True)
            path.write_text("""on talk(a) replace {
    say(narrator, text("n"));
    show_textbox(text("n2"));
    say(entity(204), text("a"), text("b"));
    show_textbox(text("c"));
}
on talk(b) replace {
    show_textbox(text("d"));
    set_dialog_owner(6);
    show_textbox(text("e"));
}
""")
            self.assertEqual(named_keys(root), {'a', 'b', 'c', 'e'})
            self.assertEqual(narrator_keys(root), {'n'})

    def test_physical_rows_respect_named_narrator_and_custom_boxes(self):
        from tools.dws.text.profiles import textbox_overflows
        script = '\n'.join([
            'SET_DIALOG_OWNER TAMER', 'SHOW_TEXTBOX', ' "a{br}b"', ' "c"', ' "lost"',
            'SET_DIALOG_OWNER 255', 'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "fits"',
            'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "d"', ' "lost"',
            'SET_TEXTBOX_SIZE 0, 20, 2', 'SHOW_TEXTBOX', ' "a"', ' "b"', ' "lost"',
            'END_SECTION', 'SHOW_TEXTBOX', ' "a"', ' "b"', ' "c"', ' "fits"'])
        self.assertEqual(list(textbox_overflows(script)), [
            (3, ['a', 'b', 'c', 'lost']), (4, ['a', 'b', 'c', 'd', 'lost']), (2, ['a', 'b', 'lost'])])

    def test_story_build_rejects_physical_overflow(self):
        import pathlib, tempfile
        from dws.basebuild import check_named_pages
        from dws.diag import DwsError
        with tempfile.TemporaryDirectory() as run:
            path = pathlib.Path(run, 'scn/script_121.scn.txt')
            path.parent.mkdir()
            path.write_text('SET_DIALOG_OWNER 255\nSHOW_TEXTBOX\n "a{br}b{br}c{br}d{br}lost"\n')
            with self.assertRaisesRegex(DwsError, '5 rows in a 4-row box'):
                check_named_pages(run, 'pt-br')
            path.write_text('SET_DIALOG_OWNER 6\nSHOW_TEXTBOX\n "greeting"\nSHOW_TEXTBOX\n "offer"\n')
            check_named_pages(run, 'pt-br')

    def test_compiled_tournament_arrays_are_not_dialogue_pages(self):
        from tools.dws.text.profiles import textbox_overflows, UNPACKED_SCRIPTS
        script = '\n'.join(['.section 10 table', '.section 11 dialogue', 'table:', 'SHOW_TEXTBOX',
                             ' "a"', ' "b"', ' "c"', ' "d"', ' "e"', ' "f"', ' "g"', 'END_SECTION',
                             'dialogue:', 'SET_DIALOG_OWNER 6', 'SHOW_TEXTBOX',
                             ' "a"', ' "b"', ' "c"', ' "lost"'])
        for sid in UNPACKED_SCRIPTS:
            self.assertEqual(list(textbox_overflows(script, sid)), [(3, ['a', 'b', 'c', 'lost'])])
        self.assertEqual(len(list(textbox_overflows(script, 121))), 2)

    def test_page_audit_detects_the_reported_demimeramon_cut(self):
        from tools.localize.check import BE, dialogue_layout, page_problems
        from dws.textbank import TextBank
        previous = dict(BE.FONT)
        try:
            BE.FONT.update(extra=True, chars=frozenset(BE.EXTRA_ORDER), name='b')
            key = 's121.sec5.u0'
            reported = [['Oi, oi. Conhece as cartas', 'Digimon? Coleciono cartas de',
                         'Meramon. Traga uma, e eu', 'compro por 1500 Bits!']]
            rendered, limit = dialogue_layout(key, reported, TextBank(source='ours'), {}, {key})
            self.assertEqual(page_problems(key, rendered, limit), ['page 1: 4 rows in a 3-row box'])
            for narrator, expected in [(False, True), (True, False)]:
                rendered, limit = dialogue_layout('mod.line', reported, TextBank(source='ours'), {}, set(),
                                                 True, 'the narrator' if narrator else 'npc (Agumon)')
                self.assertEqual(bool(page_problems('mod.line', rendered, limit)), expected)
            rendered, limit = dialogue_layout('custom', [['a{br}b', 'c']], TextBank(source='ours'),
                                             {'custom': (240, 2)}, set())
            self.assertTrue(page_problems('custom', rendered, limit))
        finally:
            BE.FONT.clear()
            BE.FONT.update(previous)

    def test_all_dialogue_pages_fit_every_language_and_font(self):
        from tools.localize.check import audit_pages, LANGUAGES, FONTS
        result = audit_pages()
        self.assertEqual(result['errors'], [])
        self.assertEqual(set(result['coverage']), {lang + ':' + font for lang in LANGUAGES for font in FONTS})
        self.assertTrue(all(count['entries'] > 4000 and count['pages'] >= count['entries']
                            for count in result['coverage'].values()))

    def test_demimeramon_offer_keeps_every_word_in_both_script_banks(self):
        import json
        from tools.localize.check import BE, ROOT, LANGUAGES, FONTS, dialogue_layout, page_problems
        from dws.textbank import TextBank, join_rows
        previous = dict(BE.FONT)
        try:
            key = 's121.sec5.u0'
            for lang in LANGUAGES:
                source = 'ours' if lang == 'en' else lang
                value = json.loads((ROOT / 'text' / source / 'dialogue/lava-cave.json').read_text())[key]
                for font in FONTS:
                    BE.FONT.update(extra=True, chars=frozenset(BE.EXTRA_ORDER), name=font)
                    rendered, limit = dialogue_layout(key, value, TextBank(lang, source), {}, {key})
                    self.assertEqual(page_problems(key, rendered, limit), [], (lang, font))
                    self.assertEqual(join_rows(row for page in rendered for row in page),
                                     join_rows(row for page in value for row in page), (lang, font))
                    self.assertIn('1500', rendered[-1][-1], (lang, font))
                    self.assertTrue(all(BE.fits(row) for page in rendered for row in page), (lang, font))
        finally:
            BE.FONT.clear()
            BE.FONT.update(previous)

    def test_every_shipped_bank_fits_both_fonts_and_preserves_references(self):
        from tools.localize.check import audit, LANGUAGES
        from unittest.mock import patch
        with patch('fontgen.base_font', side_effect=AssertionError('audit must not read disc bitmaps')):
            result = audit()
        # The developer-only examples and starter mods have English only and are
        # deliberately audited/reported too; they are not part of the everything recipe.
        self.assertEqual(len(result['notes']), 14)
        self.assertTrue(all(e['file'].startswith(('story/mods/examples/text/', 'story/mods/starter/text/'))
                            for e in result['notes']))
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['entries']), len(LANGUAGES) * 2)

    def test_runtime_arguments_are_variables_and_card_species_are_bounded(self):
        from tools.localize.check import BE, expand_references
        previous = dict(BE.FONT)
        try:
            BE.FONT.update(extra=True, chars=frozenset(BE.EXTRA_ORDER), name='original')
            names = {'main.ITEM_NAMES.1': 'Long item name', 'main.ITEM_NAMES.110': 'Egg'}
            species = {3: 'Agumon', 60: 'HerculesKabuterimon', 224: 'MetalGreymonVaccine',
                       300: 'WWWWWWWWWWWWWWWWWWW'}
            self.assertEqual(expand_references('{item 110}', names, species, {3, 60}), 'Long item name')
            self.assertEqual(expand_references('{digimon 249}', names, species, {3, 60}), 'HerculesKabuterimon')
            self.assertEqual(expand_references('{digimon 103}', names, species, {3, 60}), 'MetalGreymonVaccine')
        finally:
            BE.FONT.clear()
            BE.FONT.update(previous)

    def test_guide_requirement_labels_leave_room_for_the_live_value(self):
        import json
        from tools.localize.check import ROOT, LANGUAGES
        from tools.localize.executable.bank import list_width
        from tools.fontgen import text_width
        for language in LANGUAGES:
            names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
            for font in ('b', 'original'):
                for key, need in [('DISCIPLINE', 90), ('TECHS', 35), ('HAPPINESS', 100)]:
                    from tools.localize.check import ui_width
                    # chartCardRender now draws separate label/need/have columns.
                    # Indented bonus labels start at 49; needs end at 194, have at 280.
                    label = names['main.CHART_STR_' + key]
                    need_width = ui_width(str(need) + '+', font, language)
                    self.assertLessEqual(ui_width(label, font, language), 194 - 49 - need_width - 4,
                                         (language, font, key))

    def test_failed_technique_inheritance_keeps_its_negation(self):
        import json
        from tools.localize.check import ROOT, strings
        for language, wording in [('it', 'non è stata ereditata'), ('pt-br', 'não foi herdada')]:
            for file, key in [('maphead', 'm1240.u7'), ('unused', 's000.sec1240.u7')]:
                bank = json.loads((ROOT / 'text' / language / 'dialogue' / (file + '.json')).read_text())
                self.assertIn(wording, ' '.join(strings(bank[key])).lower())

    def test_packed_player_labels_keep_their_initial_letters_in_their_crops(self):
        from tools.localize.check import player_strip_problems
        key = 'main.MAIN_D_80123A60'
        self.assertTrue(player_strip_problems(key, 'Nome   Nível       Criados'))
        self.assertFalse(player_strip_problems(key, 'Nome     Nível       Criados'))
        key = 'main.MAIN_D_80123A98'
        self.assertTrue(player_strip_problems(key, 'Itens         Medalhas'))
        self.assertFalse(player_strip_problems(key, 'Itens          Medalhas'))

    def test_battle_obedience_message_fits_the_result_box(self):
        import json, re
        from tools.localize.check import ROOT, LANGUAGES
        from tools.fontgen import metrics
        for language in LANGUAGES:
            names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
            value = names.get('btl.BTL_STR_LISTENS_TO', '#C1Will obey this command!#W')
            for font in ('b', 'original'):
                row = re.sub(r'#[A-Z][0-9]*', '', value)
                advances = metrics(font)
                self.assertLessEqual(sum(advances.get(c, advances['?']) for c in row), 156, (language, font))

    def test_battle_mp_bonus_is_measured_after_concatenation(self):
        import json
        from tools.localize.check import ROOT, LANGUAGES, battle_mp_problems
        for language in LANGUAGES:
            names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
            for font in ('b', 'original'):
                self.assertFalse(battle_mp_problems(names, font, language), (language, font))
        portuguese = dict(names, **{'btl.BTL_STR_MP_CONSUMPTION_BONUS': '#C1Uso de MP ',
                                  'btl.BTL_STR_REDUCED_BY': '-',
                                  'btl.BTL_STR_MP_BONUS_PERCENT': ' por cento!#W'})
        self.assertTrue(battle_mp_problems(portuguese, 'original'))

    def test_packed_tech_titles_stay_in_their_semantic_columns(self):
        import json
        from tools.localize.check import ROOT, LANGUAGES, packed_ui_slices
        key = 'main.MAIN_D_80123900'
        self.assertNotEqual(packed_ui_slices(key, 'Gesetzt  FinalTechnik '),
                            ['Gesetzt', 'Final', 'Technik'])
        for language in LANGUAGES[1:]:
            names = json.loads((ROOT / 'text' / language / 'names.json').read_text())
            if language == 'zh-hans':
                from tools.localize.executable.chinese_layout import align
                names = {k: align(k, v) for k, v in names.items() if not k.startswith('_')}
            titles = packed_ui_slices(key, names[key], language)
            tabs = packed_ui_slices('main.MAIN_D_801238A0', names['main.MAIN_D_801238A0'], language)
            self.assertEqual(titles[1], '必殺' if language == 'ja' else '必杀' if language == 'zh-hans' else 'Final')
            self.assertEqual(titles[2], tabs[1], language)
        self.assertEqual(packed_ui_slices('main.MAIN_D_801238A0', '状態         わざ'), ['状態', 'わざ'])

    def test_named_english_pages_are_compiled_instead_of_an_inline_snapshot(self):
        import json, tempfile
        from pathlib import Path
        from tools.dws import build
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'story/mods/fixture'
            (folder / 'src').mkdir(parents=True)
            (folder / 'text').mkdir()
            layout = [['Received', '{item 93}.']]
            (folder / 'text/en.json').write_text(json.dumps({'deal': layout}))
            path = folder / 'src/test.py'
            path.write_text('from dw import *\narea = screen(3)\n@area.on_enter(when=trigger(5))\ndef enter():\n    narrator.say(t("deal"))\n')
            prog = build.compile_sources([str(path)], 'mods', lang='en', text_source='ours')
            self.assertEqual(prog.bank.data['fixture:deal'], layout)
            self.assertIn('fixture:deal', prog.used_text)
            code = str(prog.b.scripts)
            self.assertIn('Received', code)
            self.assertIn('{item 93}', code)

    def test_chinese_crops_check_emitted_cells_and_keep_rejecting_overflow(self):
        from tools.localize.check import packed_ui_problems, player_strip_problems, naming_label_problems
        from tools.localize.executable.chinese_layout import align
        import json
        from tools.localize.check import ROOT
        names = json.loads((ROOT / 'text/zh-hans/names.json').read_text())
        for key in ('main.MAIN_D_80123A3C', 'main.MAIN_D_80123AB0', 'main.MAIN_D_80123AE4'):
            self.assertEqual(packed_ui_problems(key, align(key, names[key]), 'zh-hans'), [])
        key = 'main.MAIN_D_80123A60'
        self.assertEqual(player_strip_problems(key, align(key, names[key]), 'zh-hans'), [])
        self.assertTrue(player_strip_problems(key, names[key], 'zh-hans'))
        self.assertTrue(packed_ui_problems('main.MAIN_D_801238A0', '选' * 30, 'zh-hans'))
        self.assertTrue(naming_label_problems('shop.MAIN_D_80134600', '退格确定', 'zh-hans'))
        self.assertFalse(naming_label_problems('shop.MAIN_D_80134600', names['shop.MAIN_D_80134600'], 'zh-hans'))

    def test_tall_boxes_are_read_from_the_authored_source(self):
        boxes = custom_boxes()
        self.assertEqual(boxes['s009.sec82.u0'], (236, 7))
        self.assertEqual(boxes['s208.sec82.u0'], (260, 8))
        self.assertEqual(boxes['s208.sec82.u1'], (260, 10))


if __name__ == '__main__':
    unittest.main()
