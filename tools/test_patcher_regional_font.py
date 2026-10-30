"""Regional glyph sources, authored fallbacks and strict generated-byte controls."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import codecopy
import dwpatch as dw
import fontcopy
from tools import fontgen


def fixture():
    codes = [0x8141, 0x8142, 0x8145, 0x8146, 0x8148, 0x8149, 0x8158, 0x815b]
    # Deliberately different button glyphs; last entry is a mutable sentinel.
    codes += [0x817e, 0x81a2, 0x8260]
    codes += [0] * (992 - len(codes))
    rows = [struct.pack('<11H', *([0xffff ^ (i << 4)] * 11)) for i in range(992)]
    return b'prefix' + struct.pack('<992H', *codes) + b''.join(rows)


def decode(tables, index):
    words = struct.unpack('<256H', tables['LATIN_ROW_WORDS'])
    counts = struct.unpack('<16H', tables['LATIN_ROW_COUNTS'])
    bit = struct.unpack_from('<H', tables['LATIN_GLYPH_OFFSETS'], index * 2)[0]
    rows = []
    for _ in range(11):
        code = first = pos = 0
        for length in range(1, 16):
            code = code * 2 + ((tables['LATIN_GLYPH_BITS'][bit // 8] >> (7 - bit % 8)) & 1)
            bit += 1
            count = counts[length]
            if code - first < count:
                rows.append(words[pos + code - first]); break
            pos += count; first = (first + count) * 2
        else:
            raise AssertionError('undecodable glyph')
    width = struct.unpack_from('<H', tables['LATIN_GLYPH_WIDTHS'], index * 2)[0]
    return struct.pack('<12H', *rows, width)


class RegionalFontTests(unittest.TestCase):
    def test_regional_code_lookup_buttons_and_authored_fallback(self):
        raw = fixture()
        glyphs, codes, evidence = fontcopy.regional_glyphs(raw, 'jp1', fontgen)
        for code, source_index in ((0x81a2, 8), (0x817e, 9), (0x8260, 10)):
            got = glyphs[codes.index(code)*24:codes.index(code)*24+24]
            self.assertEqual(got[:22], raw[6+1984+source_index*22:6+1984+(source_index+1)*22])
            self.assertEqual(got[22:], b'\x0c\0')
        index = codes.index(0x8261)  # B absent from this player's synthetic disc
        rows = fontgen.load_font_txt(fontgen.FONT_B)['B'][1]
        self.assertEqual(glyphs[index*24:index*24+22], struct.pack('<11H', *(fontgen.row_word(r) for r in rows)))
        self.assertIn(index, evidence['missing'])
        self.assertEqual(glyphs[codes.index(0x8140)*24:codes.index(0x8140)*24+24], b'\xff'*22+b'\x04\0')

    def test_all_original_glyphs_roundtrip_through_native_decoder(self):
        raw = fixture()
        glyphs, _, _ = fontcopy.regional_glyphs(raw, 'eu', fontgen)
        tables, _ = fontcopy.regional_tables(raw, 'eu', fontgen)
        for index in range(79):
            self.assertEqual(decode(tables, index), glyphs[index*24:(index+1)*24])
        self.assertEqual({k: len(v) for k,v in tables.items()}, fontcopy.CAPACITIES)

    def test_missing_truncated_ambiguous_code_tables_fail_closed(self):
        raw = fixture()
        for bad in (b'', raw[:100], raw + raw):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                fontcopy.regional_tables(bad, 'eu', fontgen)

    def test_sentinel_never_supplies_a_missing_glyph(self):
        raw = bytearray(fixture())
        struct.pack_into('<H', raw, 6+991*2, 0x8261)
        glyphs, codes, evidence = fontcopy.regional_glyphs(raw, 'eu', fontgen)
        self.assertIn(codes.index(0x8261), evidence['missing'])

    def test_capacity_overflow_and_incomplete_layout_are_rejected(self):
        tables, _ = fontcopy.regional_tables(fixture(), 'eu', fontgen)
        tables['LATIN_GLYPH_BITS'] += b'x'
        with self.assertRaisesRegex(ValueError, 'exceeds native capacity'):
            fontcopy.pad_tables(tables)
        with self.assertRaisesRegex(ValueError, 'incomplete regional'):
            fontcopy.generated_tail([], fixture(), 'eu')

    def test_native_layout_requires_current_capacities(self):
        objects = [dict(section='.rodata.'+name, offset=i*5000, length=size, source='src/main/font.c')
                   for i, (name,size) in enumerate(fontcopy.CAPACITIES.items())]
        layout = fontcopy.native_layout(objects, b'', fontgen)
        self.assertEqual(len(layout), 5)
        objects[0]['length'] -= 1
        with self.assertRaisesRegex(ValueError, 'stale'):
            fontcopy.native_layout(objects, b'', fontgen)

    def test_generated_font_bytes_cannot_be_subtraction_or_a_byte_palette(self):
        original = fixture()
        tables, _ = fontcopy.regional_tables(original, 'eu', fontgen)
        layout, tail = [], b''
        for name, data in tables.items():
            layout.append([len(tail), name, len(data)]); tail += data
        e = dict(size=len(tail), sha1=hashlib.sha1(tail).hexdigest(), font_layout=layout, bases={})
        copies, at = [], 0
        for offset, name, size in layout:
            copies.append([offset, size, len(original)+at]); at += size
        controls, diff, extra = codecopy.generate_linker_words([[0,len(tail),0]], b'', tail,
            len(original), [], copies, tail_size=len(tail))
        e['bases']['eu'] = dict(source='BOOT', source_sha1=hashlib.sha1(original).hexdigest(),
            control=controls, diff=[0,len(diff)], extra=[len(diff),len(extra)])
        self.assertEqual(set(diff), {0})
        self.assertEqual(extra, b'')
        self.assertEqual(dw.apply_binary_delta(e,'eu',lambda _:original,diff),tail)
        bad = bytearray(diff); bad[0] = 1
        with self.assertRaises(dw.PatchError):
            dw.apply_binary_delta(e,'eu',lambda _:original,bad)
        bad = copy.deepcopy(e); bad['font_layout'][0][0] = 1
        with self.assertRaises(dw.PatchError):
            dw.apply_binary_delta(bad,'eu',lambda _:original,diff)


if __name__ == '__main__':
    unittest.main()
