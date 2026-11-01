"""Pin native encoded lengths, padding aliases and source dialogue alignment."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from localize.executable import bank, padding; from dws.text import extract, repage
from dws import backend as B


class TextSources(unittest.TestCase):
    def test_native_encoded_lengths_and_button_labels(self):
        self.assertEqual(bank.encoded_len('Aéあ🙂', {'é': 0xf040}), 7)
        self.assertEqual('×△'.translate(bank.SJIS_LABELS), '△×')
        self.assertEqual(bank.ascii_glyphs('250%', {'２': 1, '％': 2}), '250％')
        self.assertEqual(bank.ascii_glyphs('A{player}B', {'Ａ': 1, 'Ｂ': 2}), 'Ａ{player}Ｂ')

    def test_padding_uses_encoded_size_and_all_language_alias_identity(self):
        banks = [dict(font={'é': 1}, text={'a': 'éé', 'b': 'éé', 'c': 'aaa', 'missing': 'x'}),
                 dict(font={'é': 1}, text={'a': 'aaa', 'b': 'aaa', 'c': 'bbb'})]
        got = padding.merge(banks)
        self.assertEqual(got['text']['a'], 'éé')
        self.assertEqual(got['aliases'], {'a': 'a', 'b': 'a', 'c': 'c'})
        self.assertTrue(got['identity'])
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            padding.merge([banks[0], dict(font={'é': 2}, text={})])

    def test_spanish_punctuation_preserves_decimal_points(self):
        self.assertEqual(extract.tidy('hambre.¿Tienes 1.5?', {'id': 'es-fan'}), 'hambre. ¿Tienes 1.5?')
        self.assertEqual(extract.tidy('hambre.¿Tienes', {'id': 'jp1'}), 'hambre.¿Tienes')

    def test_repage_restores_font_even_after_failure(self):
        before = dict(B.FONT)
        with patch.object(B, 'fits', side_effect=RuntimeError('fixture')):
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                repage.fits_in('b', 'text')
        self.assertEqual(B.FONT, before)


if __name__ == '__main__':
    unittest.main()
