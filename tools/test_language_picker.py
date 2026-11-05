"""Language picker assets and modal bounds on the ordinary 2 MB renderer."""
import json
from pathlib import Path
import struct
import unittest

from tools.localize import language_flags as flags
from tools.fontgen import text_width

ROOT = Path(__file__).resolve().parents[1]


class PickerAssets(unittest.TestCase):
    def test_flag_runs_reproduce_every_pixel_including_china(self):
        palettes, offsets, runs = flags.tables()
        self.assertEqual(len(offsets), 9)
        self.assertEqual(len(flags.payload('palette')), 9 * 16)
        for language in range(9):
            cursor = offsets[language]
            for y in range(16):
                row = []
                while len(row) < 24:
                    run = runs[cursor]
                    cursor += 1
                    self.assertGreater(run & 31, 0)
                    row += [palettes[language][run >> 5]] * (run & 31)
                self.assertEqual(row, [flags.pixel(language, x, y) for x in range(24)])
            self.assertEqual(cursor, offsets[language + 1] if language < 8 else len(runs))
        self.assertEqual(set(flags.pixel(8, x, y) for x in range(24) for y in range(16)),
                         {0xda2430, 0xffd23a})

    def test_resident_name_matches_the_licensed_subset_and_stays_small(self):
        font = json.loads((ROOT / 'tools/font/chinese.json').read_text())['glyphs']
        self.assertEqual(flags.chinese_name(), font['中'][1:] + font['文'][1:])
        self.assertEqual(len(flags.payload('chinese_name')), 48)
        self.assertEqual(list(struct.unpack('<24H', flags.payload('chinese_name'))), flags.chinese_name())

    def test_popup_has_four_bounded_rows_in_every_current_language(self):
        for language in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
            names = json.loads((ROOT / f'text/{language}/names.json').read_text())
            rows = [names[f'main.MOD_OPT_STR_CHINESE_RAM_{i}'] for i in range(4)]
            self.assertEqual(len(rows), 4, language)
            for row in rows:
                self.assertTrue(row.strip(), language)
                if language != 'zh-hans':
                    for font in ('original', 'a', 'b'):
                        self.assertLessEqual(text_width(row, font), 256, (language, font, row))


if __name__ == '__main__':
    unittest.main()
