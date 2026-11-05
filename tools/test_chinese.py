"""Offline proofs for Chinese authoring; these do not claim runtime support."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools import chinese as zh
from tools import chinese_resources as resources


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

    def test_append_only_codebook_keeps_existing_codes(self):
        chars = zh.repertoire()
        needed = zh.used_repertoire()
        self.assertTrue(set(needed) <= set(chars))
        book = zh.read_json(zh.ROOT / 'tools/font/chinese-codes.json')
        self.assertEqual(chars, book['characters'])
        self.assertEqual(zh.encode('亚古兽', chars), zh.encode('亚古兽', chars + ['𠮷']))

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

    def test_unpacked_rows_reserve_their_terminator_unit(self):
        text = 'A ' * 30
        pages = zh.wrap(text, self.glyphs, packed=False)
        for row in pages[0]:
            self.assertLessEqual(zh.row_metrics(row, self.glyphs, packed=False)[1], 62)


class ChineseContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = zh.build_font(zh.read_json(zh.ROOT / zh.FONT_PATH), zh.repertoire())
        cls.patch = b'DWLP' + struct.pack('<I', 1) + struct.pack('<II', 0x80100000, 4) + b'text'

    def test_resources_share_sectors_but_keep_story_and_sign_routes(self):
        data = resources.build(b'runtime', self.font, self.patch, [
            dict(name='DG.SCN', story=0, data=b'extended'),
            dict(name='DG.SCN', story=1, data=b'original'),
            dict(name='FI_INFO.TIM', signs=True, data=b'extended')])
        self.assertEqual(resources.validate(data), 3)
        records = [resources.ENTRY.unpack_from(data, resources.DIRECTORY_OFFSET+i*16) for i in range(3)]
        self.assertEqual(records[0][2], records[2][2])
        self.assertNotEqual(records[0][2], records[1][2])
        self.assertEqual(records[2][1], 2)
        broken = bytearray(data);broken[resources.FONT_OFFSET+40] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            resources.validate(broken)

    def test_component_replay_rebuilds_regional_geometry_and_rejects_alias_changes(self):
        from tools.patcher import chinese_container as container
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'lang').mkdir()
            (root / 'lang/one.SCN').write_bytes(b'extended')
            (root / 'lang/two.SCN').write_bytes(b'original')
            rows = [dict(name='DG.SCN', story=0, signs=False, source='lang/one.SCN'),
                    dict(name='DG.SCN', story=1, signs=False, source='lang/two.SCN')]
            plan = dict(CHINESE_RESOURCES=rows, CHINESE_OVL=[])
            data = resources.build(b'runtime', self.font, self.patch,
                [{**r, 'data': (root / r['source']).read_bytes()} for r in rows])
            recipe, parts = container.components(data, plan, root)
            self.assertEqual(container.rebuild(recipe, parts), data)
            # The developer CLI starts with tools/patcher on sys.path, without the repository root.
            import json
            import subprocess
            import sys
            (root / 'input.bin').write_bytes(data)
            (root / 'plan.json').write_text(json.dumps(plan))
            standalone = (
                'import sys,json;from pathlib import Path;'
                f'sys.path.insert(0,{str(zh.ROOT / "tools/patcher")!r});'
                'import chinese_container as C;'
                f'r=Path({str(root)!r});b=(r/"input.bin").read_bytes();'
                'p,f=C.components(b,json.loads((r/"plan.json").read_text()),r);'
                'assert C.rebuild(p,f)==b')
            subprocess.run([sys.executable, '-I', '-c', standalone], cwd=tmp, check=True,
                           capture_output=True, text=True)
            parts['@zh/lang/one.SCN'] = b'regional' * 900
            changed = container.rebuild(recipe, parts)
            self.assertEqual(resources.validate(changed), 2)
            self.assertNotEqual(len(changed), len(data))
            with self.assertRaisesRegex(ValueError, 'alias'):
                resources.build(b'runtime', self.font, self.patch, [
                    dict(name='A.SCN', source='same', data=b'A'),
                    dict(name='B.SCN', source='same', data=b'B')])

    def test_disc_assembler_checks_components_then_omits_virtual_files(self):
        import hashlib
        import sys
        import types
        from unittest.mock import patch
        sys.path.insert(0, str(zh.ROOT / 'tools/patcher'))
        import dwpatch as dw
        parts = {'@zh/module': b'runtime', '@zh/font': self.font,
                 '@zh/names': bytes(resources.NAME_COUNT*resources.NAME_SIZE), '@zh/writes': self.patch}
        recipe = dict(format=1, module='@zh/module', font='@zh/font', names='@zh/names',
                      patch='@zh/writes', resources=[])
        blob = bytearray()
        ops = {}
        for key, data in parts.items():
            ops[key] = [['l', len(blob), len(data)]]
            blob.extend(data)
        ops['SCN/LANGZH.BIN'] = [['j', 0, 0, resources.PREFIX_SIZE]]
        payload = dict(files=ops, sources=[], blob=blob, license=[], layout='', chinese=[recipe],
                       sha1={k:hashlib.sha1(v).hexdigest() for k,v in parts.items()})
        layout = types.SimpleNamespace(files=lambda: ['SCN/LANGZH.BIN'])
        writer = types.SimpleNamespace(Layout=lambda _:layout,
            write=lambda lay, files, out, **kw:(files,None))
        base = types.SimpleNamespace(key='us')
        with patch.object(dw, '_iw', return_value=writer):
            _, files = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(list(files), ['SCN/LANGZH.BIN'])
            self.assertEqual(resources.validate(files['SCN/LANGZH.BIN']), 0)
            payload['sha1']['@zh/module'] = 'invalid'
            with self.assertRaisesRegex(dw.PatchError, '@zh/module'):
                dw.build_disc3(payload, base, {}, 'unused', progress=False)

    def test_bad_routes_writes_and_names_are_refused_before_output(self):
        common = (b'runtime', self.font, self.patch)
        row = dict(name='DG.SCN', data=b'data')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            resources.build(*common, [row, row])
        patch = b'DWLP' + struct.pack('<I', 1) + struct.pack('<II', 0x801fffff, 4) + b'bad!'
        with self.assertRaisesRegex(ValueError, 'outside resident'):
            resources.build(b'runtime', self.font, patch, [])
        names = bytearray(resources.NAME_COUNT*resources.NAME_SIZE)
        names[:20] = b'A'*20
        with self.assertRaisesRegex(ValueError, 'terminator'):
            resources.build(*common, [], names)
        names[:20] = b'A'*18+b'\xa0\0'
        with self.assertRaisesRegex(ValueError, 'splits'):
            resources.validate_names(names)

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
