"""The new technique rows' art keeps to its own cells of SYSTEM_W."""
import struct
import unittest

from tools.localize.build import tim_entries
from tools.localize.fi_info import overlaps
from tools.localize.status_art import TAG_RECT, BATTLES_RECT, ICON_RECT
from tools.localize.systemw import (CARE_BUTTON_RECTS, CARE_BUTTON_GUARD_RECTS, CARE_BUTTON_CLUT_RECT,
                                    CHINESE_MENU_CELLS, CHINESE_MENU_SIZE, ZH_FILTH_CELL)
from tools.localize import tech_rows_art as art


def cells(language):
    out = [(u, v, 12, 12) for pair in art.ICON_CELLS for u, v in pair] + [art.CLUT_RECT]
    out += [(u, v, 12, 12) for u, v in art.icon_cells(language)] + [art.NEW_CLUT_RECT]
    if language == 'en':
        wide = {key[0]: cell for key, cell in art.WIDE_CELLS.items()}
        out += [wide.get(word, (u, v, *art.EN_CELL)) for word, u, v in art.EN_NAMES]
    return out


class TechRowsArt(unittest.TestCase):
    def test_tiles_and_palette(self):
        colours, tiles = art.art()
        self.assertEqual(len(colours), 16)
        self.assertEqual([len(pair) for pair in tiles], [2, 2, 2])
        for pair in tiles:
            for tile in pair:
                self.assertEqual((len(tile), {len(row) for row in tile}), (12, {12}))
        # each row draws with its own colours only (and the grey tile's)
        for (low, high), pair in zip(((0, 2), (3, 5), (6, 9)), tiles):
            used = {n for tile in pair for row in tile for n in row if n < 10}
            self.assertTrue(used and used <= set(range(low, high + 1)))
        self.assertEqual(art.CLUT_ID, 253 << 6 | 22)

    def test_cells_are_nobodys(self):
        taken = [TAG_RECT, BATTLES_RECT, ICON_RECT, CARE_BUTTON_CLUT_RECT, *CARE_BUTTON_RECTS, *CARE_BUTTON_GUARD_RECTS]
        taken += [(128, 110, 38, 12), (166, 110, 28, 12), (194, 110, 34, 12), (96, 84, 64, 12), (160, 84, 38, 12)]
        chinese = [(u, v, *CHINESE_MENU_SIZE) for _, u, v in CHINESE_MENU_CELLS.values()]
        mine = cells('fr') + list(art.WIDE_CELLS.values())
        for i, rect in enumerate(mine):
            self.assertFalse(any(overlaps(rect, other) for other in taken + mine[:i]), rect)
        # Chinese has its menu words in the corner the other languages use, and its own cells for what came last
        theirs = cells('zh-hans') + list(art.ZH_CELLS.values()) + [ZH_FILTH_CELL]
        for i, rect in enumerate(theirs):
            self.assertFalse(any(overlaps(rect, other) for other in taken + chinese + theirs[:i]), rect)
        # the English names sit where only a Spanish-layout label goes, which the English texture does not have
        english = cells('en')
        for i, rect in enumerate(english):
            self.assertFalse(any(overlaps(rect, other) for other in [TAG_RECT, BATTLES_RECT, ICON_RECT] + english[:i]), rect)
        row = art.ES_ROW
        self.assertFalse(any(overlaps(row, rect) for rect in mine))
        self.assertEqual({r[1:] for r in art.OTHER_CELLS.values()}, {(41, 34, 10)})

    def test_stamp_writes_only_its_cells(self):
        header = struct.pack('<II', 16, 8) + struct.pack('<IHHHH', 524, 96, 488, 16, 16)
        blank = bytearray(header + bytes(512) + struct.pack('<IHHHH', 16396, 320, 128, 64, 128) + bytes([255]) * 16384)
        start = tim_entries(blank)[0][0]
        for language in ('en', 'es', 'ja'):
            data = bytearray(blank)
            art.stamp(data, language=language)
            allowed = {start + y * 128 + x // 2 for u, v, w, h in cells(language)
                       for y in range(v, v + h) for x in range(u, u + w)}
            self.assertEqual(len(data), len(blank))
            self.assertTrue({i for i, (a, b) in enumerate(zip(blank, data)) if a != b} <= allowed)
            again = bytearray(data)
            art.stamp(again, language=language)
            self.assertEqual(again, data)

    def test_english_names_fit(self):
        widths = art.english_widths()
        self.assertEqual(len(widths), 5)
        self.assertTrue(all(w <= art.EN_CELL[0] for w in widths[:3]))
        self.assertTrue(all(w <= cell[2] for w, cell in zip(widths[3:], art.WIDE_CELLS.values())))


if __name__ == '__main__':
    unittest.main()
