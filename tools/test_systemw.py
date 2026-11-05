"""Raster regressions: small labels retain strokes and use unused atlas space."""
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.localize import labels
from tools.localize.systemw import relocated_rect


class RasterLabels(unittest.TestCase):
    def test_minification_keeps_a_stroke_on_an_unsampled_source_row(self):
        # A faint five-row stem surrounds a one-row horizontal bar. Nearest
        # neighbor at height two misses the bar; area coverage preserves it.
        glyph = ['#...', '####', '#...', '#...', '#...'] + ['....'] * 6
        with patch.object(labels, 'glyphs', return_value={'X': glyph}):
            old = labels.mask('X', 4, 2)
            new = labels.mask('X', 4, 2, preserve=True)
        self.assertGreater(sum(map(sum, new)), sum(map(sum, old)))

    @unittest.skipUnless(Path('extracted/ETCDAT/SYSTEM_W.TIM').exists(), 'needs the source disc texture')
    def test_atlas_cells_are_transparent_in_the_source_texture(self):
        from tools.localize.textures.systemw.idx import load
        _, _, pixel, _, _ = load('extracted/ETCDAT/SYSTEM_W.TIM')
        for en, es in [('POWER', 'POTENCIA'), ('RANG', 'ALC.'), ('SPEC', 'EFECTO'),
                       ('TECH. DATA', 'DATOS TÉC.'), ('RANG', 'ALCANCE')]:
            u, v, w, h = relocated_rect(dict(en=en, es=es))
            self.assertEqual({pixel(x, y) for x in range(u, u+w) for y in range(v, v+h)}, {15})

    def test_chinese_partner_labels_keep_native_strokes_and_clear_the_icons(self):
        import json
        from tools.localize.systemw import CHINESE_MENU_CELLS, CHINESE_MENU_SIZE, check_chinese_menu_cells
        check_chinese_menu_cells()
        font = json.loads(Path('tools/font/chinese.json').read_text())['glyphs']
        icon_x = {1:20, 2:56, 3:91, 4:20, 5:56, 6:91, 7:20}
        for index, (text, u, v) in CHINESE_MENU_CELLS.items():
            expected = [[not (font[c][y+1] & (0x8000 >> x)) for c in text for x in range(12)] for y in range(12)]
            occupied = [y for y, row in enumerate(expected) if any(row)]
            expected = expected[occupied[0]:occupied[-1]+1]
            self.assertEqual(labels.mask(text, *CHINESE_MENU_SIZE, preserve=True), expected, text)
            # renderRectPolyFT4 drops the atlas-edge blank column at U256.
            # The native glyph strokes all lie before it.
            drawn_width = min(CHINESE_MENU_SIZE[0], 255-u)
            self.assertFalse(any(any(row[drawn_width:]) for row in expected), text)
            self.assertLess(v + 128 + CHINESE_MENU_SIZE[1], 256)
            # 20px icons are followed by 3px air and a 13px label. The next
            # icon row begins 40px later, leaving four further clear pixels.
            self.assertLessEqual(20 + 3 + CHINESE_MENU_SIZE[1], 40)
            self.assertLessEqual(CHINESE_MENU_SIZE[0], 35)
            self.assertGreaterEqual(icon_x[index]-2, 0)

    @unittest.skipUnless(Path('extracted/ETCDAT/SYSTEM_W.TIM').exists(), 'needs source texture')
    def test_chinese_menu_cells_are_unused_in_the_original_atlas(self):
        from tools.localize.systemw import CHINESE_MENU_CELLS, CHINESE_MENU_SIZE
        from tools.localize.textures.systemw.idx import load
        _, _, pixel, _, _ = load('extracted/ETCDAT/SYSTEM_W.TIM')
        for _, u, v in CHINESE_MENU_CELLS.values():
            w,h = CHINESE_MENU_SIZE
            self.assertEqual({pixel(x,y) for y in range(v,v+h) for x in range(u,u+w)}, {15})

    def test_atlas_cells_do_not_overlap_each_other_or_native_sprites(self):
        keys = [('POWER', 'POTENCIA'), ('RANG', 'ALC.'), ('SPEC', 'EFECTO'),
                ('TECH. DATA', 'DATOS TÉC.'), ('RANG', 'ALCANCE')]
        occupied = set()
        for en, es in keys:
            u, v, w, h = relocated_rect(dict(en=en, es=es))
            self.assertEqual(h, 12)
            self.assertLessEqual(u+w, 256)
            self.assertLessEqual(v+h, 128)
            cells = {(x, y) for x in range(u, u+w) for y in range(v, v+h)}
            self.assertFalse(cells & occupied)
            self.assertTrue(all((128 <= x and 110 <= y < 122) or
                                (96 <= x < 212 and 84 <= y < 96) for x, y in cells))
            occupied |= cells


if __name__ == '__main__':
    unittest.main()
