"""Data-copy ranges, regional mapping patches and bounded multi-disc reads."""
import io
import hashlib
import json
import struct
import shutil
import tempfile
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import datacopy
import dwpatch as dw
import fontcopy


class DataCopyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('c++'), 'developer search needs C++17')
    def test_fresh_scanner_resolves_secondary_rows_and_sector_boundaries(self):
        logical = random.Random(87).randbytes(4096)
        target = logical[2039:2083]
        raw = bytearray(2352 * 2)
        raw[24:2072] = logical[:2048]
        raw[2376:4424] = logical[2048:]
        empty = bytes(len(raw))
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for i, data in enumerate((raw, empty, raw)):
                path = Path(td) / f'disc {i}.bin'
                path.write_bytes(data)
                paths.append(str(path))
            views = [bytes(raw), logical, empty, bytes(4096), bytes(raw), logical]
            with patch.object(datacopy.audit, 'DiscFiles') as reader:
                reader.return_value.read.side_effect = lambda row: views[row]
                found = datacopy.find_sources(target, [(0, len(target))],
                    {'us': paths[0], 'eu': paths[1]}, {'dcb': paths[2]}, td)
            for key, spans in found.items():
                self.assertEqual(sum(b-a for a,b,*_ in spans), len(target))
                for a,b,view,off in spans:
                    source = logical if view.endswith('@userdata') else raw
                    self.assertEqual(source[off:off+b-a], target[a:b])
                    if key == 'eu': self.assertTrue(view.startswith('@disc:dcb:'))

    def test_secondary_sources_fill_gaps_without_overwriting_base(self):
        primary = [[10, 30, '@raw', 100], [50, 60, '@userdata', 200]]
        secondary = [[0, 20, '@disc:dcb:@raw', 300], [20, 70, '@disc:dw2:@raw', 400]]
        self.assertEqual(datacopy.merge_spans(primary, secondary), [
            [0, 10, '@disc:dcb:@raw', 300], primary[0], [30, 50, '@disc:dw2:@raw', 410],
            primary[1], [60, 70, '@disc:dw2:@raw', 440]])

    def test_short_literal_uses_a_verified_whole_file_context(self):
        target = random.Random(82).randbytes(64)
        p = dict(files={'ART': [['c', 0, 0, 20], ['l', 0, 5], ['c', 0, 25, 39]]},
                 sources=['ART'], blob=target[20:25], code=[], reloc={'eu': {}}, license=[])
        def found(blob, ranges, bases, source_discs, work):
            self.assertEqual(blob, target)
            self.assertEqual(ranges, [(0, 64)])
            return {'us': [[0, 64, '@raw', 100]], 'eu': [[0, 64, '@disc:dcb:@raw', 200]]}
        with patch.object(datacopy, 'find_sources', side_effect=found):
            stats = datacopy.copy_payload(p, {'us': 'us', 'eu': 'eu'}, targets={'ART': target})
        self.assertEqual(stats['copied'], 5)
        self.assertEqual(p['blob'], b'')
        self.assertEqual(p['code'], [[1, 120, 5]])
        self.assertEqual(p['reloc']['eu']['0'], [['@disc:dcb:@raw', 220, 5]])

    def test_mapping_data_splits_preserve_unavailable_pixels(self):
        data = bytes(range(80))
        mp = {'eu': {'files': {'ART': {'source': 'ART', 'ops': [{'copy': [0, 2]}, {'data': data.hex()}, {'fill': [3, 2]}]}}}}
        image = types.SimpleNamespace(read=lambda q: b'AB', f=io.BytesIO())
        with patch.object(datacopy.audit.iw, 'Image', return_value=image), \
             patch.object(datacopy, 'find_sources', return_value={'eu': [[12, 62, '@disc:dcb:@raw', 7]]}):
            stats = datacopy.copy_mappings(mp, {'eu': 'unused'})
        self.assertEqual(stats['after'], 30)
        ops = mp['eu']['files']['ART']['ops']
        self.assertEqual(ops[2], {'disc_copy': ['@disc:dcb:@raw', 7, 50]})
        result = dw.apply_ops(ops, b'AB', lambda path, off, n: data[10:60])
        self.assertEqual(result, b'AB' + data + bytes([3, 3]))
        with self.assertRaises(dw.PatchError):
            dw.apply_ops(ops, b'AB')

    def test_boot_rename_comes_from_the_build_file_plan(self):
        target = b'BOOT = cdrom:\\PATCHED.EXE;1\nTCB = 4\n'
        sources = {key: b'BOOT = cdrom:\\' + boot + b';1\nTCB = 4\n'
                   for key, boot in [('us', b'BASE-A.EXE'), ('eu', b'BASE-B.EXE')]}
        payload = dict(files={'SYSTEM.CNF': [['l', 0, len(target)]]}, blob=target + b'own',
            sources=[], code=[], reloc={'eu': {}}, fix={}, layout='',
            table={'file': 'PATCHED.EXE'}, license=[['l', len(target), 3]],
            sha1={'SYSTEM.CNF': hashlib.sha1(target).hexdigest()})
        def image(path):
            return types.SimpleNamespace(read=lambda q: sources[path], f=io.BytesIO())
        with patch.object(datacopy.audit.iw, 'Image', side_effect=image):
            stats = datacopy.copy_boot_config(payload, {'us': 'us', 'eu': 'eu'}, {'SYSTEM.CNF': target})
        self.assertEqual(stats['generated_literals'], len(target))
        self.assertEqual(payload['blob'], b'own')
        self.assertEqual(payload['sources'], ['@boot:PATCHED.EXE'])
        # This fixture has no executable sector table; exercise the real operation reader.
        del payload['table']
        writer = types.SimpleNamespace(Layout=lambda x: x,
            write=lambda lay, got, out, **kw: (None, dict(got)))
        for key in sources:
            base = types.SimpleNamespace(key=key, map=None if key=='us' else {}, code=lambda q: sources[key])
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(got['SYSTEM.CNF'], target)
        with self.assertRaises(dw.PatchError):
            dw.boot_config(b'no executable field', 'PATCHED.EXE')

    def test_secondary_payload_copy_uses_registered_disc_on_every_base(self):
        target = b'verified source bytes'
        payload = dict(sources=['@disc:dcb:@raw'], code=[[0, 3, len(target)]], blob=b'', layout='',
            files={'CODE': [['r', 0]]}, license=[], fix={},
            reloc={'eu': {'0': [['@disc:dcb:@raw', 3, len(target)]]}},
            sha1={'CODE': hashlib.sha1(target).hexdigest()})
        writer = types.SimpleNamespace(Layout=lambda x: x,
            write=lambda lay, got, out, **kw: (None, dict(got)))
        for key in ('us', 'eu'):
            base = object.__new__(dw.BaseDisc)
            base.key, base.map = key, None if key == 'us' else {}
            base.img = types.SimpleNamespace(f=io.BytesIO(b'wrong primary source'))
            base.source_discs = {'dcb': 'mounted player image'}
            base._copy_images = {'dcb': types.SimpleNamespace(f=io.BytesIO(b'pre' + target + b'post'))}
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(got['CODE'], target)

    def test_localized_japanese_mapping_reads_disc_copies(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'MAP').write_bytes(b'abcxyz')
            base = object.__new__(dw.BaseDisc)
            base.mapping = {'files': {'MAP': {'ops': [{'copy': [0, 3]}, {'disc_copy': ['@raw', 3, 3]}],
                'regions': [], 'masked_sha1': hashlib.sha1(b'abcDEF').hexdigest()}}}
            base._loc = td
            base.img = types.SimpleNamespace(f=io.BytesIO(b'xxxDEF'))
            self.assertEqual(base.localized('MAP'), b'abcDEF')

    def test_secondary_reads_are_bounded_and_cross_sector_headers(self):
        logical = random.Random(39).randbytes(4096)
        raw = bytearray(2352 * 2)
        raw[24:2072] = logical[:2048]
        raw[2376:4424] = logical[2048:]
        base = object.__new__(dw.BaseDisc)
        base.img = types.SimpleNamespace(f=io.BytesIO(b'base'))
        base.source_discs = {'dcb': 'provided by player'}
        image = types.SimpleNamespace(f=io.BytesIO(raw))
        base._copy_images = {'dcb': image}
        self.assertEqual(base.read_copy('@disc:dcb:@userdata', 2040, 30), logical[2040:2070])
        self.assertEqual(base.read_copy('@disc:dcb:@raw', 2330, 30), bytes(raw[2330:2360]))
        for path, off, n in [('@disc:dw2:@raw', 0, 1), ('@raw', -1, 1), ('@raw', 3, 20),
                             ('@disc:dcb:@userdata', 4090, 20)]:
            with self.assertRaises(dw.PatchError):
                base.read_copy(path, off, n)

    def test_glyph_plan_finds_current_offsets_and_reports_absence(self):
        glyphs = random.Random(45).randbytes(79 * 24)
        plans = fontcopy.glyph_plan(glyphs, {'us': b'prefix' + glyphs, 'eu': glyphs[:24]})
        self.assertEqual(plans['us']['missing_bytes'], 0)
        self.assertEqual(plans['us']['sources'][10], [6 + 10 * 24, 24])
        self.assertEqual(plans['eu']['missing'], list(range(1, 79)))
        self.assertEqual(plans['eu']['missing_bytes'], 78 * 24)
        moved = fontcopy.glyph_plan(glyphs, {'us': b'new build prefix' + glyphs})
        self.assertNotEqual(moved['us']['sources'][10], plans['us']['sources'][10])

    def test_player_font_generation_follows_moved_linker_tables(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools import fontgen
        codes = json.loads(Path(fontgen.ORIGINAL_METRICS).read_text())['codes']
        # Synthetic single-pixel glyphs; no game pixels in this regression.
        glyphs = struct.pack('<12H', *([0xffef] * 11 + [12])) * 79
        original = glyphs + struct.pack('<79H', *codes)
        generator = types.SimpleNamespace(GLYPH_DATA=0, EXE_BASE=0, CHAR_TO_GLYPH_TABLE=len(glyphs))
        for key in ('load_extra', 'font_tables', 'japanese_huffman'):
            setattr(generator, key, getattr(fontgen, key))
        arrays = fontcopy.generate(glyphs, codes, generator)
        target = b'new function bytes' + b''.join(arrays.values()) + b'new story text'
        payload = dict(files={'SLUS_010.32': [['l', 0, len(target)]]}, blob=target,
                       license=[], sources=[], code=[], reloc={}, fix={}, layout='',
                       sha1={'SLUS_010.32': hashlib.sha1(target).hexdigest()})
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'build.map'
            pos = len(b'new function bytes')
            lines = []
            for name, value in arrays.items():
                lines.append(f' .rodata.{name}\n 0x{pos:x} 0x{len(value):x} build/src/main/font.c.o')
                pos += len(value)
            path.write_text('\n'.join(lines))
            stats = fontcopy.prepare(payload, original, {'us': ('SLUS', b'moved' + original)}, path, generator)
            self.assertEqual(stats['copied_literals'], sum(map(len, arrays.values())))
            self.assertEqual(payload['blob'], b'new function bytesnew story text')
            self.assertNotIn('codes', payload['font'])
            self.assertEqual(payload['font']['code_sources']['us'], ['SLUS', 5 + len(glyphs), 158])
            base = types.SimpleNamespace(key='us', map=None, tool_root=str(Path(fontgen.ROOT)),
                                         code=lambda p: b'moved' + original)
            writer = types.SimpleNamespace(Layout=lambda x: x,
                write=lambda lay, got, out, **kw: (None, dict(got)))
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(got['SLUS_010.32'], target)
            blocked = dict(files={'SLUS_010.32': [['l', 0, len(target)]]}, blob=target)
            stats = fontcopy.prepare(blocked, original,
                {'us': ('SLUS', original), 'eu': ('SLES', b'no such glyphs')}, path, generator)
            self.assertEqual(blocked['blob'], target)
            self.assertNotIn('font', blocked)
            self.assertEqual(stats['missing_by_base']['eu'], len(glyphs))
            no_codes = dict(files={'SLUS_010.32': [['l', 0, len(target)]]}, blob=target)
            stats = fontcopy.prepare(no_codes, original,
                {'us': ('SLUS', original), 'eu': ('SLES', glyphs)}, path, generator)
            self.assertEqual(stats['missing_by_base']['eu'], 0)
            self.assertEqual(stats['code_table_missing_by_base']['eu'], 158)
            self.assertNotIn('font', no_codes)


if __name__ == '__main__':
    unittest.main()
