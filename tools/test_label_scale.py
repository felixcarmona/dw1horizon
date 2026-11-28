"""Small UI labels are drawn at their letters' own size: no label's glyphs are resampled to fit a cell.

tools/localize/labels.py refuses a word too big for its cell (LabelOverflow) instead of resampling it; only the labels
listed in labels.OPEN keep the old resampled look, and each of them must really not fit."""
import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from tools.localize import labels
from tools.localize.catalog import LANGUAGES, word

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, 'extracted', '')


def fits(rows, w, h, shadow=1):
    return len(rows) + shadow <= h and len(rows[0]) + shadow <= w


class LabelScale(unittest.TestCase):
    def test_mask_refuses_a_word_too_big_instead_of_resampling_it(self):
        glyph = ['#...', '####', '#...', '#...', '#...'] + ['....'] * 6
        with patch.object(labels, 'glyphs', return_value={'X': glyph}):
            # (a glyph keeps one blank column after its ink)
            self.assertEqual(labels.mask('X', 5, 5), [[c == '#' for c in row + '.'] for row in glyph[:5]])
            for room in ((5, 4), (4, 5)):
                with self.assertRaises(labels.LabelOverflow):
                    labels.mask('X', *room)

    def test_every_open_label_really_does_not_fit_in_font_b(self):
        self.assertTrue(labels.OPEN)
        for (language, text, (u, v, w, h)), why in labels.OPEN.items():
            with self.subTest(language=language, text=text):
                self.assertIn(language, LANGUAGES)
                self.assertTrue(why)
                with self.assertRaises(labels.LabelOverflow):
                    labels.mask(text, w, h)   # not even with no room left for padding

    def test_the_triangle_menu_push_and_mode_words_fit_their_cells_in_the_pixel_fonts(self):
        from tools.localize.fi_info import CELLS, SHARED_SIZES
        pf, F = labels.pixfont(), labels.systemw_fonts()[0]
        for col, language in enumerate(LANGUAGES):
            if language not in labels.LATIN:
                continue
            for e, (text, _, _) in CELLS.items():
                with self.subTest(language=language, text=text):
                    self.assertTrue(any(fits(labels.compose(font, word(text, language)), *SHARED_SIZES[e])
                                        for font in (pf.LABEL6, pf.LABEL6_COMPACT)
                                        if all(c in font for c in word(text, language))))
            push = ('APPUYEZ', 'DRÜCKEN', 'PREMI', 'おす', 'PREM', '按下')[col]
            self.assertTrue(any(fits(labels.compose(font, push), 31, 9) for font in (pf.BUBBLE7,)
                                if all(c in font for c in push)), push)
            mode = ('COMBAT', 'KAMPF', 'LOTTA', 'バトル', 'COMBAT', '战斗')[col]
            self.assertTrue(fits(labels.compose(F.STAT, mode), 51, 8), mode)

    def test_the_battle_banner_has_one_block_per_pixel_of_the_word_at_its_own_size(self):
        F = labels.systemw_fonts()[0]
        for language in LANGUAGES:
            with self.subTest(language=language):
                banner = labels.battle_banner(language)
                rows = (labels.compose(F.STAT, banner['text']) if language in labels.LATIN
                        else labels.native(banner['text'], 7))
                self.assertEqual(banner['blocks_drawn'], sum(map(sum, rows)))
                self.assertEqual(len(banner['positions']), 155)

    @unittest.skipUnless(os.path.exists(EXTRACTED + 'ETCDAT/SYSTEM_W.TIM'), 'needs the USA disc in extracted/')
    def test_every_language_resamples_only_its_open_labels(self):
        from tools.localize import build as L
        original = labels._legacy_scaled
        os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
        for language in LANGUAGES:
            with self.subTest(language=language):
                used = set()

                def legacy(text, maxw, maxh, preserve=False):
                    used.add(text)
                    return original(text, maxw, maxh, preserve)
                with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, 'build')) as d, \
                        patch.object(labels, '_legacy_scaled', legacy), contextlib.redirect_stdout(io.StringIO()):
                    L.build(d + '/out', EXTRACTED, scratch=d + '/scratch', language=language)
                self.assertEqual(used, {text for lang, text, _ in labels.OPEN if lang == language})


if __name__ == '__main__':
    unittest.main()
