"""Regression cases for cropped UI fields and runtime font fitting."""
import unittest
import json
from pathlib import Path

from tools.localize.ui import audit, bounds, fitted_width, name_problems, tab_problems, field_problems, confirmation_problems, answer_problems


class CroppedUI(unittest.TestCase):
    def test_shipped_fields_fit_every_language_and_font(self):
        self.assertEqual(audit()['errors'], [])

    def test_missing_settings_notice_has_two_bounded_advice_lines(self):
        for font in ('b', 'original', 'classic'):
            self.assertFalse(field_problems('main.MOD_NOTICE_STR_CPU', 'CPU overclock at 250%', font, 'en'))
            self.assertFalse(field_problems('main.MOD_NOTICE_STR_HEAD2', 'if you turn on these options:', font, 'en'))
        self.assertTrue(field_problems('main.MOD_NOTICE_STR_CPU', 'W' * 40, 'b', 'en'))
        self.assertTrue(field_problems('main.MOD_NOTICE_STR_HEAD2', 'W' * 80, 'b', 'en'))

    def test_notice_keeps_v007_status_words_with_measured_widths(self):
        for language, word in (('de', 'NICHT ERKANNT'), ('pt-br', 'NÃO DETECTADO')):
            for font in ('b', 'original', 'classic'):
                self.assertFalse(field_problems('main.MOD_NOTICE_STR_MISSING', word, font, language))
                self.assertTrue(field_problems('main.MOD_NOTICE_STR_MISSING', word + 'W' * 30, font, language))

    def test_notice_has_only_the_six_v007_text_rows_in_every_language(self):
        root = Path(__file__).resolve().parents[1]
        fields = {'HEAD1', 'HEAD2', 'RAM', 'CPU', 'MISSING', 'READY'}
        for language in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
            names = json.loads((root / 'text' / language / 'names.json').read_text())
            notice = {key.removeprefix('main.MOD_NOTICE_STR_'): value
                      for key, value in names.items() if key.startswith('main.MOD_NOTICE_STR_')}
            self.assertEqual(set(notice), fields, language)

    def test_reported_tab_cannot_use_full_portuguese_label(self):
        self.assertTrue(tab_problems('main.MAIN_D_801238A0', 'Estado  Técnicas', 'original', 'pt-br'))

    def test_reported_finisher_keeps_its_full_name(self):
        name = 'Síndrome do Pesadelo'
        self.assertGreater(bounds(name, 'original', 'pt-br')[1], 132)
        self.assertLessEqual(fitted_width(name, 'original', 'pt-br'), 136)
        self.assertFalse(name_problems('main.MOVE_NAMES.96', name, 'original', 'pt-br'))

    def test_fitting_does_not_hide_new_font_overflow(self):
        self.assertTrue(name_problems('main.MOVE_NAMES.14', 'Tempestade de Confusão', 'b', 'pt-br'))
        self.assertTrue(name_problems('main.MOVE_NAMES.96', 'W' * 30, 'original', 'pt-br'))

    def test_whole_yes_no_words_fit_smallest_crop_in_every_font(self):
        for font in ('b', 'original', 'classic'):
            self.assertFalse(answer_problems('Sim Não', font, 'pt-br', 36, centred=True))
            self.assertFalse(answer_problems('はい いいえ', font, 'ja', 36, centred=True))
        self.assertTrue(answer_problems('Sim', 'b', 'pt-br', 36))
        self.assertTrue(answer_problems('Yes WWWWWW', 'original', 'en', 36, centred=True))

    def test_confirmation_answers_must_share_second_row(self):
        self.assertTrue(confirmation_problems('m1240.u0', [["D’accord ?", 'Oui', 'Non']], 'b', 'fr'))
        self.assertFalse(confirmation_problems('m1240.u0', ['Tudo certo?', 'Sim Não'], 'original', 'pt-br'))
        self.assertTrue(confirmation_problems('m1240.u0', ['W' * 20, 'Yes No'], 'original', 'en'))

    def test_shop_item_limit_is_narrower_than_inventory(self):
        self.assertTrue(field_problems('main.ITEM_NAMES.123', 'Chave da geladeira', 'b', 'pt-br'))
        self.assertFalse(field_problems('main.ITEM_NAMES.123', 'Chave geladeira', 'b', 'pt-br'))


if __name__ == '__main__':
    unittest.main()
