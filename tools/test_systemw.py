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
