"""Regression cases for cropped UI fields and runtime font fitting."""
import unittest

from tools.localize.ui import audit, bounds, fitted_width, name_problems, tab_problems


class CroppedUI(unittest.TestCase):
    def test_shipped_fields_fit_every_language_and_font(self):
        self.assertEqual(audit()['errors'], [])

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


if __name__ == '__main__':
    unittest.main()
