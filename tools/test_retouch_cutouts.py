"""A retouch of a disc background (dwmap.py bg) must also refresh the map's cut-outs drawn over the characters, or they
keep showing the old picture over the new one (Overdell's notch, 2026-11-03)."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dwmap  # noqa: E402


def tim(x, w, h, pixels):
    clut = struct.pack('<I4H256H', 524, 0, 480, 256, 1, *([0] * 256))
    image = struct.pack('<I4H', 12 + w * h * 2, x, 0, w, h) + bytes(pixels)
    return struct.pack('<II', 16, 9) + clut + image


def background(cluts, fill):
    t = dwmap.TfsFile.__new__(dwmap.TfsFile)
    t.hdr_w, t.hdr_h, t.tail = 128, 128, b''
    t.cluts = [list(c) for c in cluts]
    t.tiles = [[struct.pack('<HH', 0, 0), bytearray(fill)]]
    return t


class RefreshCutouts(unittest.TestCase):
    def setUp(self):
        day = [0x1000 + i for i in range(256)]; day[255] = 0x8000          # DGHA01: 255 keys the cut-outs, 0x8000 by day
        night = [0x0800 + i for i in range(256)]; night[255] = 0
        self.cluts = [day, night]
        old = bytearray(128 * 128)
        for y in range(128):
            for x in range(128): old[y * 128 + x] = 10
        self.before = background(self.cluts, old)
        new = bytearray(old)
        for y in range(8, 16):
            for x in range(8, 16): new[y * 128 + x] = 20         # the retouch
        new[9 * 128 + 9] = 255                                     # black in the new art
        self.after = background(self.cluts, new)
        # a 16x16 cut-out at (4, 4) holding the old picture; its first column is a hole
        px = bytearray(256 * 16)
        for y in range(16):
            for x in range(16): px[y * 256 + x] = 255 if x == 0 else 10
        m = dwmap.MapFile.__new__(dwmap.MapFile)
        m.width = m.height = 1; m.tiles = [0]
        m.tims = [tim(384, 128, 16, px)]
        m.sprites = [dict(texX=0, texY=0, width=16, height=16, x=0, y=0, z=0, clut=-1, transparency=1)]
        m.instances = [dict(frames=[0] + [-1] * 7, times=[0] * 8, x=4, y=4, flag=0)]
        self.m = m

    def texel(self, x, y):
        t = dwmap.TIM(self.m.tims[0]); return t.pixels[(y - 4) * t.w * 2 + (x - 4)]

    def test_the_cutout_shows_the_new_art_and_keeps_its_holes(self):
        report, conflicts = dwmap.refresh_cutouts(self.m, self.before, self.after)
        self.assertEqual(conflicts, [])
        self.assertEqual(self.texel(12, 12), 20)                  # over the retouch: the new pixel
        self.assertEqual(self.texel(5, 5), 10)                    # outside it: untouched
        self.assertEqual(self.texel(4, 10), 255)                  # a hole stays a hole
        self.assertNotIn(self.texel(9, 9), dwmap.cutout_holes(self.after))   # new black is drawn, not a hole
        self.assertEqual(report, {0: 64})

    def test_every_retouched_pixel_under_a_cutout_renders_like_the_background(self):
        dwmap.refresh_cutouts(self.m, self.before, self.after)
        holes = dwmap.cutout_holes(self.after)
        for y in range(8, 16):
            for x in range(8, 16):
                v, b = self.texel(x, y), self.after.tiles[0][1][y * 128 + x]
                if b in holes: continue
                for c in self.after.cluts: self.assertEqual(c[v], c[b], (x, y))

    def test_holes_follow_the_semi_transparency_mode(self):
        self.assertIn(255, dwmap.cutout_holes(self.after, 1))     # additive: black with the bit adds nothing
        self.assertNotIn(255, dwmap.cutout_holes(self.after, 4))  # opaque: 0x8000 is drawn black


class TimeOfDayModel(unittest.TestCase):
    def test_a_grey_night_is_learned_from_the_palettes(self):
        day = [dwmap.rgb_to_bgr555((i * 37) % 256, (i * 91) % 256, (i * 53) % 256) or 0x8000 for i in range(256)]
        def night(c):                                     # half as bright, half the saturation, a blue cast
            r, g, b = dwmap.bgr555_to_rgb(c); y = (r + g + b) / 3
            return dwmap.rgb_to_bgr555(*(int(min(255, (0.5 * v + 0.5 * y) * 0.5 + k)) for v, k in ((r, 0), (g, 0), (b, 20))))
        t = background([day, [night(c) for c in day]], bytes(range(256)) * 64)
        m = dwmap.MapFile.__new__(dwmap.MapFile); m.width = m.height = 1; m.tiles = [0]
        M = dwmap.time_of_day_model(t, m)[1]
        for c in ((200, 120, 40), (30, 200, 90)):
            want = dwmap.bgr555_to_rgb(night(dwmap.rgb_to_bgr555(*c)))
            for a, b in zip(dwmap.apply_model(M, c), want): self.assertLess(abs(a - b), 12, (c, want))


if __name__ == '__main__':
    unittest.main()
