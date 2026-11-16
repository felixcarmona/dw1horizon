"""Status art contracts: all languages fit; the two old icon draws cannot overlap."""
from pathlib import Path
import struct
import unittest

from tools.languages import CODES
from tools.localize.status_art import TAG_RECT, ICON_RECT, VIRUS, tag, stamp, crop_tables
from tools.localize.build import tim_entries


class StatusArt(unittest.TestCase):
    def test_reviewed_authored_raster_pins(self):
        import json
        from tools.localize.status_art import ROOT, art_pins
        self.assertEqual(json.loads((ROOT / 'content/localized/status/pins.json').read_text()), art_pins())

    def test_new_labels_cannot_silently_overwrite_the_tag(self):
        from tools.localize.status_art import check_cells
        u,v,w,h = TAG_RECT
        with self.assertRaisesRegex(ValueError, 'overlaps status tag'):
            check_cells([dict(en='future label', es='future label', u=u, v=v, w=w, h=h)])

    def test_all_languages_have_complete_tag_outlines_and_fit(self):
        for language in CODES:
            with self.subTest(language=language):
                rows = tag(language)
                self.assertEqual((len(rows[0]), len(rows)), (36, 10))
                ink = {(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == 2}
                self.assertTrue(ink)
                self.assertTrue(all(0 < x < 35 and 0 < y < 9 for x, y in ink))
                for x, y in ink:
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            self.assertIn(rows[y+dy][x+dx], (1, 2))

    def test_crops_repurpose_cap_and_leave_exactly_one_icon_in_every_bank(self):
        # Include English, where crop generation used to preserve every native row.
        row = '\t{ 0xff77, 0x004f, 0x0009, 0x000b, 0x00f0, 0x0025 },\n'
        source = 'IconRect STATS_VIEW_ELEMENTS[21] = {\n'
        source += '\n'.join(d + '\n' + row*21 for d in ('#if ES', '#elif JA', '#else')) + '\n#endif\n};'
        result = crop_tables(source)
        self.assertEqual(crop_tables(result), result)
        self.assertEqual(result.count('0x0045, 0xffde, 0x0024, 0x000a, 0x006c, 0x0048'), 3)
        self.assertEqual(result.count('0xff76, 0x0054, 0x000b, 0x000b, 0x002c, 0x0074'), 3)

    def test_stamp_changes_only_crops_and_preserves_file_and_palette_sizes(self):
        # Synthetic TIM: no private player assets needed for the write-boundary test.
        header = struct.pack('<II', 16, 8) + struct.pack('<IHHHH', 524, 96, 488, 16, 16)
        data = bytearray(header + bytes(512) + struct.pack('<IHHHH', 16396, 320, 128, 64, 128) + bytes([255])*16384)
        before = bytes(data)
        start = tim_entries(data)[0][0]
        allowed = {start + y*128 + x//2 for u,v,w,h in (TAG_RECT, ICON_RECT)
                   for y in range(v,v+h) for x in range(u,u+w)}
        for language in CODES:
            after = bytearray(before)
            stamp(after, language=language)
            self.assertEqual(len(after), len(before))
            self.assertTrue({i for i,(a,b) in enumerate(zip(before,after)) if a != b} <= allowed)
            self.assertEqual(after[:start], before[:start])
            again = bytearray(after)
            stamp(again, language=language)
            self.assertEqual(again, after)
        self.assertEqual({len(row) for row in VIRUS}, {11})
        self.assertFalse(any('C' in row or 'D' in row for row in VIRUS))

    @unittest.skipUnless(Path('extracted/ETCDAT/SYSTEM_W.TIM').exists(), 'needs player texture')
    def test_tag_slot_is_unused_in_native_art_and_clear_of_live_localized_crops(self):
        from tools.localize.textures.systemw.idx import load
        from tools.localize.fi_info import overlaps
        from tools.localize.systemw import CHINESE_MENU_CELLS, CHINESE_MENU_SIZE, CARE_BUTTON_RECTS
        import json
        _, _, pixel, _, _ = load('extracted/ETCDAT/SYSTEM_W.TIM')
        u,v,w,h = TAG_RECT
        self.assertEqual({pixel(x,y) for y in range(v,v+h) for x in range(u,u+w)}, {15})
        crops = list(CARE_BUTTON_RECTS) + [(u,v,*CHINESE_MENU_SIZE) for _,u,v in CHINESE_MENU_CELLS.values()]
        for item in json.loads(Path('tools/localize/textures/systemw/rects.json').read_text()):
            if item['en'] != 'SPEED (alternative)':
                crops.append(tuple(item[k] for k in ('u','v','w','h')))
        self.assertFalse(any(overlaps(TAG_RECT, rect) for rect in crops))


if __name__ == '__main__':
    unittest.main()
