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


    def test_drawn_texels_are_opaque(self):
        """a texel meant to be seen never reads colour 0 (transparent), and the zigzags never 0x8000-style colours:
        the egg box draws its sprites semi-transparent (additive), where a texel with the STP bit shows the background"""
        E = self.E
        for k in range(4):
            row = self.new.row(E.NEW_ROW + k)
            for y in range(32):
                for x in range(E.ICON_W):
                    i = self.new.px(E.ICON_U + E.ICON_W * k + x, E.ICON_V + y)
                    if i:
                        self.assertNotEqual(row[i], 0, (k, x, y, i))
        yuki = self.new.row(E.NEW_ROW + 2)
        zig = {E.ZIG_ICON} | set(E.ZIG_OVER.values())
        for i in zig:
            self.assertTrue(yuki[i] and not yuki[i] & 0x8000, (i, hex(yuki[i])))
        icon = {self.new.px(E.ICON_U + E.ICON_W * 2 + x, E.ICON_V + y) for x in range(E.ICON_W) for y in range(32)}
        self.assertIn(E.ZIG_ICON, icon)
        skin = {self.new.px(u, v) for u in range(96) for v in range(48)}
        self.assertTrue(set(E.ZIG_OVER.values()) & skin)
        for v in range(48):                      # every skin texel the YukimiBotamon egg can show is opaque
            for u in range(96):
                i = self.new.px(u, v)
                if i:
                    self.assertNotEqual(yuki[i], 0, (u, v, i))


if __name__ == '__main__':
    unittest.main()
