"""The four new eggs drawn into TAMA.TIM leave everything the original eggs read as it was (tools/egg_art.py)."""
from pathlib import Path
import unittest

SRC = Path('extracted/ETCDAT/TAMA.TIM')


@unittest.skipUnless(SRC.exists(), 'needs the source disc texture')
class EggArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import egg_art
        cls.E = egg_art
        cls.old = egg_art.Tim(bytearray(SRC.read_bytes()))
        cls.new = egg_art.Tim(bytearray(egg_art.build(SRC.read_bytes())))

    def test_same_size_and_header(self):
        self.assertEqual(len(self.old.d), len(self.new.d))
        self.assertEqual(self.old.d[:20], self.new.d[:20])

    def test_original_rows_read_the_same_colours(self):
        for y in (488, 490, 491, 492, 493, 494, 495, 496):
            self.assertEqual(self.old.row(y), self.new.row(y), y)
        # row 489 (the wave egg) gains the zigzag indices, each the colour of the index it covers
        old, new = self.old.row(489), self.new.row(489)
        self.assertEqual(old[:6], new[:6])
        for src, dst in self.E.ZIG_OVER.items():
            self.assertEqual(new[dst], old[src])

    def test_original_eggs_look_the_same(self):
        """every texel of the 3D skin and the old icons shows the colour it showed, under each original row"""
        E = self.E
        for x in range(256):
            for y in range(80):
                a, b = self.old.px(x, y), self.new.px(x, y)
                if a == b:
                    continue
                if E.ICON_U <= x < E.ICON_U + 4 * E.ICON_W and E.ICON_V <= y < E.ICON_V + 32:
                    self.assertEqual(a, 0, (x, y))      # the new icons: on empty texels
                    continue
                self.assertLess(x, 96, (x, y))
                self.assertEqual(self.new.row(489)[b], self.old.row(489)[a], (x, y))
                self.assertLess(y, 48, (x, y))      # only the wave egg's UVs reach above v 48

    def test_new_rows_and_icons(self):
        for k in range(4):
            row = self.new.row(self.E.NEW_ROW + k)
            self.assertTrue(all(row[1:]), k)            # no transparent entry past index 0
            icon = {self.new.px(self.E.ICON_U + 28 * k + x, self.E.ICON_V + y) for x in range(28) for y in range(32)}
            self.assertIn(0, icon)
            self.assertGreater(len(icon), 5)


if __name__ == '__main__':
    unittest.main()
