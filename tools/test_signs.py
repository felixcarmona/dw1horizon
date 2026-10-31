"""Sign foregrounds with an opaque palette zero and a transparent colour elsewhere."""
import struct
import unittest
from types import SimpleNamespace

from tools.localize.signs import Pixels, sprite_paste


class SpriteTransparency(unittest.TestCase):
    def paste(self, palette_alpha):
        pixels = bytes((0, 1, 255, 2))
        palette = [0x0482, 0x7FFF, 0x001F] + [0x0482] * 252 + [0]
        tim = (struct.pack('<III4H', 0x10, 9, 524, 0, 480, 256, 1)
               + struct.pack('<256H', *palette)
               + struct.pack('<I4H', 12 + len(pixels), 384, 0, 2, 1) + pixels)
        m = SimpleNamespace(
            tims=[tim],
            sprites=[dict(clut=-1, texX=0, texY=0, width=4, height=1)],
            instances=[dict(frames=[0], x=0, y=0, flag=0)],
        )
        t = SimpleNamespace(cluts=[palette])
        sprite_paste(m, t, Pixels(4, 1, [(255, 255, 255)] * 4),
                     Pixels(4, 1, [255] * 4), 0, 0, palette_alpha=palette_alpha)
        return m.tims[0][-4:]

    def test_opaque_zero_is_repainted_and_transparent_255_stays_clear(self):
        self.assertEqual(self.paste(True), bytes((1, 1, 255, 1)))

    def test_other_signs_retain_the_historical_index_zero_rule(self):
        self.assertEqual(self.paste(False), bytes((0, 1, 1, 1)))


if __name__ == '__main__':
    unittest.main()
