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

    def test_every_label_of_a_kind_takes_font_b_only_if_all_of_them_fit_it(self):
        # one word too big for font B sends its whole kind to the SYSTEM_W font, so labels seen together share one
        # style (KRAFT in font B beside EFFEKT in the small header font ran into the technique page's values)
        fits = {'KRAFT': True, 'EFFEKT': False, 'TEMPO': True, 'FREUDE': True, 'NAME': True}
        labelled = [({'en': en}, text, (0, 0, 40, 12)) for en, text in
                    (('POWER', 'KRAFT'), ('EFFECT', 'EFFEKT'), ('SPEED', 'TEMPO'), ('HAPPINESS', 'FREUDE'),
                     ('NAME', 'NAME'))]
        with patch.object(labels, 'fits_b', lambda text, rect, padding=2: fits[text]):
            self.assertEqual(labels.font_b_kinds(labelled, 'de'), {'stat', 'tag'})
            self.assertEqual(labels.font_b_kinds(labelled, 'es'), {'small', 'stat', 'tag'})
        self.assertEqual([labels.kind(item['en']) for item, _, _ in labelled], ['small', 'small', 'stat', 'stat', 'tag'])

    @unittest.skipUnless(os.path.isdir(EXTRACTED), 'needs the extracted disc')
    def test_the_technique_page_labels_sit_where_their_crops_expect_them(self):
        # font B's nine rows plus its shadow reach the Final row's value under the header; the small header font is
        # five rows (seven with a capital's accent) plus its outline. The panel draws its labels from the cell's left
        # edge and end a column before the arrow; the element names are cropped to their letters at the cell's right edge
        # (tools/localize/systemw.py crop_tables): a name drawn elsewhere in its cell is cut or stands out
        from tools.localize import build as L
        from tools.localize.build import tim_entries
        from tools.localize.systemw import LATIN_ELEMENT_CELLS, PANEL_CELLS, PANEL_LABEL_GAP, PANEL_LABEL_ROOM, TECH_CELLS
        from tools.localize.tech_rows_art import OTHER_CELLS, WIDE_CELLS
        names = {**LATIN_ELEMENT_CELLS, **OTHER_CELLS, **WIDE_CELLS}
        panel = [TECH_CELLS[key] for key in PANEL_CELLS]
        os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
        for language in labels.LATIN:
            with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, 'build')) as d, \
                    contextlib.redirect_stdout(io.StringIO()):
                L.build(d + '/out', EXTRACTED, scratch=d + '/scratch', language=language)
                data = open(os.path.join(d, 'out', language, 'ETCDAT', 'SYSTEM_W.TIM'), 'rb').read()
            start, _, w, h = tim_entries(data)[0]
            px = [v for b in data[start:start + w * h // 2] for v in (b & 15, b >> 4)]

            def ink(rect):
                u, v, cw, ch = rect
                rows = [px[(v + y) * w + u:(v + y) * w + u + cw] for y in range(ch)]
                background = max(set(sum(rows, [])), key=sum(rows, []).count)
                columns = [x for x in range(cw) if any(row[x] != background for row in rows)]
                return sum(any(c != background for c in row) for row in rows), columns[0], columns[-1] + 1
            for rect in TECH_CELLS.values():
                with self.subTest(language=language, cell=rect):
                    painted, left, right = ink(rect)
                    self.assertLessEqual(painted, 9)
                    self.assertEqual(left, 0)
                    if rect in panel:
                        self.assertLessEqual(right, PANEL_LABEL_ROOM - PANEL_LABEL_GAP)
            for (en, es), rect in names.items():
                with self.subTest(language=language, name=word(es, language)):
                    fonts, words = labels.systemw_fonts()
                    rows = words.compose(fonts.ELEM, word(es, language), gap=0)
                    drawn = [x for x in range(len(rows[0])) if any(row[x] != '.' for row in rows)]
                    at = rect[2] - labels.element_width(word(es, language))
                    self.assertEqual(ink(rect)[1:], (at + drawn[0], at + drawn[-1] + 1))

def _font_module(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# the letters the German, French, Italian and Catalan words added to the label fonts
ADDED = {
    'systemw': {'SMALL': 'WÈoKXZ', 'TAG': 'Y.', 'TAG_NARROW': 'PODS', 'TSA': 'UKZ', 'TSA_ACTIVE': 'KZ',
                'TSA_SPECIAL': 'KZ', 'STAT': 'GKMU·À!', 'ELEM': 'QÉÈÍ', 'SMALL_COMPACT': 'ÉÀ',
                'TAG_COMPACT': 'ÂÀÈ'},
    'pixfont': {'LABEL6': '.Ü', 'LABEL6_COMPACT': 'ÉÊ', 'BUBBLE7': 'KYZÜ'},
}


class AddedLetters(unittest.TestCase):
    def test_every_added_letter_reads_as_itself(self):
        # a K drawn with an H's straight right side made EFFEKT read EFFENT
        modules = {'systemw': _font_module('label_fonts', 'tools/localize/textures/systemw/fonts.py'),
                   'pixfont': _font_module('label_pixfont', 'tools/localize/textures/fi-info/pixfont.py')}
        tone = {'#': 2, 'c': 1, 'x': 1}

        def distance(a, b, weight):
            if len(a) != len(b) or any(len(r) != len(q) for r, q in zip(a, b)):
                return 99
            return sum(abs(weight(p) - weight(q)) for r, s in zip(a, b) for p, q in zip(r, s))
        for module, fonts in ADDED.items():
            for name, letters in fonts.items():
                font = getattr(modules[module], name)
                for letter in letters:
                    for other, glyph in font.items():
                        if other == letter:
                            continue
                        with self.subTest(font=name, letter=letter, other=other):
                            self.assertGreaterEqual(distance(font[letter], glyph, lambda c: tone.get(c, 0)), 2)
                            self.assertGreaterEqual(distance(font[letter], glyph, lambda c: c in tone), 1)

if __name__ == '__main__':
    unittest.main()
