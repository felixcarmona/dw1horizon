"""Regression coverage for translation loss and actual renderer constraints."""
import unittest
from tools.localize.check import control_problems, custom_boxes, runtime_tokens


class LocalizationAudit(unittest.TestCase):
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

    def test_every_shipped_bank_fits_both_fonts_and_preserves_references(self):
        from tools.localize.check import audit, LANGUAGES
        result = audit()
        # The developer-only examples mod has English only and is deliberately
        # audited/reported too; it is not part of the everything recipe.
        self.assertEqual(len(result['notes']), 7)
        self.assertTrue(all(e['file'].startswith('story/mods/examples/text/') for e in result['notes']))
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
                    label = names['main.CHART_STR_' + key] + ' ' + str(need) + '+'
                    # chartCardLine: 114px card, marker, indent, value and gap.
                    room = 114 - 18 - 6 - text_width(str(need), font) - 4
                    self.assertLessEqual(list_width(label, font), room, (language, font, key))

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
                self.assertFalse(battle_mp_problems(names, font), (language, font))
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
            titles = packed_ui_slices(key, names[key])
            tabs = packed_ui_slices('main.MAIN_D_801238A0', names['main.MAIN_D_801238A0'])
            self.assertEqual(titles[1], '必殺' if language == 'ja' else 'Final')
            self.assertEqual(titles[2], tabs[1], language)
        self.assertEqual(packed_ui_slices('main.MAIN_D_801238A0', '状態         わざ'), ['状態', 'わざ'])

    def test_tall_boxes_are_read_from_the_authored_source(self):
        boxes = custom_boxes()
        self.assertEqual(boxes['s009.sec82.u0'], (236, 7))
        self.assertEqual(boxes['s208.sec82.u0'], (260, 8))
        self.assertEqual(boxes['s208.sec82.u1'], (260, 10))


if __name__ == '__main__':
    unittest.main()
