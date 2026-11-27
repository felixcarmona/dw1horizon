"""Regional title inputs must reach derive and receive their own release hashes."""
import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest import mock

from tools import title_stamp
from tools.patcher.dwpatch import regional_derive


def title_tim(ink):
    """an 8-bit 320x256 TIM like TITLE256: transparent (255) but the pixels of ink, {(x, y): index}"""
    w, h = 320, 256
    pix = bytearray([255]) * (w * h)
    for (x, y), v in ink.items():
        pix[y * w + x] = v
    clut = struct.pack('<IHHHH', 12 + 512, 0, 480, 256, 1) + bytes(512)
    return bytearray(struct.pack('<II', 0x10, 9) + clut + struct.pack('<IHHHH', 12 + len(pix), 768, 0, w // 2, h) + pix)


class RegionalTitles(unittest.TestCase):
    def test_only_consumed_regional_inputs_require_replay(self):
        files = {'MOVIE/OP1.STR': {'how': 'own'}, 'ETCNA/TITLE256.TIM': {'how': 'own'}}
        mapping = {'files': files}
        self.assertFalse(regional_derive(None, files))
        self.assertFalse(regional_derive(mapping, ['MAP/MAP0/GCITY00.MAP']))
        self.assertTrue(regional_derive(mapping, ['ETCNA/TITLE256.TIM']))
        self.assertTrue(regional_derive(dict(files={}, localize_tool='fromjp.py'), []))

    def test_all_european_mappings_keep_title_without_canonical_pixel_ops(self):
        root = Path(__file__).resolve().parents[1]
        for region in ('eu', 'fr', 'de', 'es', 'it'):
            with self.subTest(region=region):
                mapping = json.loads((root / f'mods/base-discs/dw1-{region}.json').read_text())
                title = mapping['files']['ETCNA/TITLE256.TIM']
                self.assertEqual(title['how'], 'own')
                self.assertEqual(title['source'], 'ETCNA/TITLE256.TIM')
                self.assertNotIn('ops', title)
                self.assertTrue(regional_derive(mapping, ['ETCNA/TITLE256.TIM']))
                self.assertEqual(mapping['files']['ETCNA/TITLE2.TIM']['how'], 'same')

    def test_a_narrower_press_start_line_is_centred_alone_in_the_quad(self):
        # the European line: "Press Start Button" in columns 0-114, its language list ("English...") from column 115
        line = {(x, 245): 0 for x in (0, 114)}
        line.update({(x, y): 0 for x in range(115, 121) for y in (241, 245, 249)})
        data = title_tim(line)
        pix = len(data) - 320 * 256
        with mock.patch.dict(title_stamp.RELEASE_PRESS_START, {hashlib.sha1(data).hexdigest(): 115}):
            out = title_stamp.press_start_fit(bytearray(data))
        u, v, w, h = title_stamp.PRESS_START
        shown = {(x, y) for y in range(v, v + h) for x in range(u, u + w) if out[pix + y * 320 + x] != 255}
        self.assertEqual(shown, {(3, 245), (117, 245)})   # moved by (121 - 115) // 2, the E gone
        self.assertEqual(out[:pix], data[:pix])            # header and CLUT as they were

    def test_other_titles_are_left_alone(self):
        data = title_tim({(x, 245): 0 for x in range(0, 121)})
        self.assertEqual(title_stamp.press_start_fit(bytearray(data)), data)


if __name__ == '__main__':
    unittest.main()
