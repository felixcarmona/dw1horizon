"""Offline proofs for Chinese authoring; these do not claim runtime support."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools import chinese as zh


class ChineseFontTests(unittest.TestCase):
    def test_all_dense_codes_roundtrip_without_control_or_terminator_bytes(self):
        codes = [zh.index_to_code(i) for i in range(zh.CAPACITY)]
        self.assertEqual(len(set(codes)), 12032)
        for i, code in enumerate(codes):
            self.assertEqual(zh.code_to_index(code), i)
            self.assertNotIn(code & 255, (0, 10, 13, 32, 127))
        for bad in (-1, zh.CAPACITY):
            with self.assertRaises(ValueError):
                zh.index_to_code(bad)
        for bad in (0x9FFC, 0xA07F, 0xA0FD, 0xE040):
            with self.assertRaises(ValueError):
                zh.code_to_index(bad)

    def test_encoding_preserves_latin_digits_and_never_substitutes_missing_glyphs(self):
        self.assertEqual(zh.encode('亚A0古', ['亚', '古']), bytes.fromhex('A0404130A041'))
        with self.assertRaisesRegex(ValueError, 'no Chinese glyph'):
            zh.encode('兽', ['亚', '古'])

    def test_checked_in_font_builds_offline_and_detects_damage(self):
        font = zh.read_json(zh.ROOT / zh.FONT_PATH)
        chars = zh.repertoire()
        data = zh.build_font(font, chars)
        self.assertEqual(zh.validate_font(data), len(chars))
        self.assertEqual(data, zh.build_font(font, chars))
        self.assertEqual(len(data), 32 + 26 * (95 + len(chars)))
        for damaged in (b'', data[:31], data[:-1], data + b'\0', data[:40] + bytes([data[40] ^ 1]) + data[41:]):
            with self.assertRaises(ValueError):
                zh.validate_font(damaged)
        bad_count = bytearray(data)
        struct.pack_into('<I', bad_count, 24, zh.CAPACITY + 1)
        with self.assertRaises(ValueError):
            zh.validate_font(bad_count)

    def test_font_keeps_the_pinned_licensed_source(self):
        source = zh.read_json(zh.ROOT / 'tools/font/chinese-license/source.json')
        font = zh.read_json(zh.ROOT / zh.FONT_PATH)
        self.assertEqual(source['sha256'], zh.SOURCE_SHA256)
        self.assertEqual(font['_source_sha256'], source['sha256'])
        self.assertEqual(source['license'], 'SIL-OFL-1.1')
        for notice in ('OFL.txt', 'upstream/ark-pixel/OFL.txt', 'upstream/cubic-11/OFL.txt', 'upstream/galmuri/LICENSE.txt'):
            self.assertTrue((zh.ROOT / 'tools/font/chinese-license' / notice).is_file())

    def test_bdf_placement_keeps_bottom_row_and_refuses_clipping(self):
        template = ('STARTFONT 2.1\nFONT_ASCENT 10\nSTARTCHAR test\nENCODING 20122\n'
                    'DWIDTH 12 0\nBBX 1 1 0 {y}\nBITMAP\n80\nENDCHAR\nENDFONT\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.bdf'
            path.write_text(template.format(y=-2))
            glyph = zh.parse_bdf(path, {'亚'})['亚']
            self.assertEqual(glyph, [12] + [65535] * 11 + [32767])
            path.write_text(template.format(y=-3))
            with self.assertRaisesRegex(ValueError, 'clipped'):
                zh.parse_bdf(path, {'亚'})
            with self.assertRaisesRegex(ValueError, 'font lacks'):
                zh.parse_bdf(path, {'兽'})


class ChineseLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glyphs = zh.read_json(zh.ROOT / zh.FONT_PATH)['glyphs']

    def test_wrapping_keeps_controls_words_and_punctuation_together(self):
        text = '你' * 18 + '（亚古兽）' + '你好，世界！' * 8 + '{color 6}{partner}{color 1}HP123……'
        pages = zh.wrap(text, self.glyphs)
        rows = [row for page in pages for row in page]
        self.assertEqual(''.join(rows), text)
        for page in pages:
            self.assertLessEqual(len(page), 3)
            for i, row in enumerate(page):
                visible = zh.ESCAPE.sub('', row)
                self.assertNotIn(visible[0], zh.NO_START)
                self.assertNotIn(visible[-1], zh.NO_END)
                pixels, size = zh.row_metrics(row, self.glyphs)
                self.assertLessEqual(pixels, 228 if i == 2 else 240)
                self.assertLessEqual(size, 62)
        self.assertEqual(sum('HP123' in row for row in rows), 1)
        self.assertEqual(sum('{partner}' in row for row in rows), 1)
        with self.assertRaises(ValueError):
            zh.wrap('A' * 100, self.glyphs)

    def test_latin_keyboard_digits_have_distinct_visible_bitmaps(self):
        self.assertTrue(all(c in self.glyphs for c in zh.ASCII))
        digits = [tuple(self.glyphs[c][1:]) for c in '0123456789']
        self.assertEqual(len(set(digits)), 10)
        self.assertTrue(all(any(row != 65535 for row in digit) for digit in digits))

    def test_draft_preserves_controls_and_fits_its_authoring_boxes(self):
        report = zh.audit()
        self.assertGreater(report['translated'], 0)
        self.assertEqual(report['errors'], [])
        self.assertEqual(zh.audit_layout(), [])

    def test_audit_catches_control_loss_unknown_keys_and_untranslated_species(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(name, value):
                zh.write_json(root / name, value)
            write('text/ours/names.json', {})
            write('text/en.json', {'greeting': 'Hi {partner}!', 'missing': 'Hello'})
            write('text/zh-hans.json', {'greeting': 'Agumon来了！', 'typo': '你好'})
            write('text/zh-hans/glossary.json', {'species': {'Agumon': {'zh': '亚古兽'}}, 'avoid': {}})
            report = zh.audit(root)
            self.assertEqual(report['missing'], ['text/zh-hans.json:missing'])
            self.assertTrue(any('signature' in e for e in report['errors']))
            self.assertTrue(any('unknown key' in e for e in report['errors']))
            self.assertTrue(any('untranslated species' in e for e in report['errors']))

    def test_duplicate_keys_fail_instead_of_overwriting_a_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bank.json'
            path.write_text('{"line":"甲", "line":"乙"}')
            with self.assertRaisesRegex(ValueError, 'duplicate key'):
                zh.read_json(path)

    def test_review_uses_original_name_banks_for_executable_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = 'main.ITEM_NAMES.0'
            for path, value in (
                    ('text/ours/names.json', 'Food'),
                    ('text/zh-hans/names.json', '食物'),
                    ('text/jp/names.json', '<original & name>'),
                    ('text/jp/dialogue.json', 'wrong dialogue bank')):
                zh.write_json(root / path, {key: value})
            output = root / 'review.html'
            zh.review(output, root)
            text = output.read_text()
            self.assertIn('&lt;original &amp; name&gt;', text)
            self.assertIn('食物', text)
            self.assertNotIn('wrong dialogue bank', text)


if __name__ == '__main__':
    unittest.main()
