"""Difference records must not turn an absent table into approved source data."""
import json
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import delta_audit
import literal_gate


class DeltaAuditTests(unittest.TestCase):
    def test_composite_source_witnesses_name_the_actual_player_file(self):
        delta = dict(source='MAIN', diff=[0, 6], control=[[0, 0, 1], [6, 0, 0]])
        self.assertEqual(delta_audit.unchanged_witnesses(delta, bytes(6), b'BCDEFG', b'ABCDEFG',
            [[0, 3, 'MAIN', 0], [3, 7, 'OVERLAY', 0]]),
            [[0, 2, 'MAIN', 1], [2, 6, 'OVERLAY', 0]])

    def test_regional_buffer_witnesses_use_each_reconstructed_output(self):
        for changed in (False, True):
            originals = {'usa': b'AAAA', 'europe': b'BBBB'}
            eu = b'CCCC' if changed else originals['europe']
            entry = dict(file='SLUS_010.32', size=4,
                         sha1=hashlib.sha1(originals['usa']).hexdigest(),
                         sha1_by_base={'eu': hashlib.sha1(eu).hexdigest()}, bases={})
            for key, name, offset in [('us', 'usa', 0), ('eu', 'europe', 4)]:
                entry['bases'][key] = dict(source='BOOT', source_sha1=hashlib.sha1(originals[name]).hexdigest(),
                    diff=[offset, 4], extra=[8, 0], control=[[4, 0, 0]])
            payload = dict(blob=bytes(4) + bytes([1 if changed else 0])*4, deltas=[entry])
            def image(name):
                return types.SimpleNamespace(read=lambda _: originals[name], f=io.BytesIO())
            def find_sources(query, ranges, bases, secondary):
                self.assertEqual(query, b'AAAA' + eu)
                # A real match for the USA bytes on another source disc cannot
                # certify the distinct European output at query offset four.
                return {'us': [[0, 4, '@raw', 0]], 'eu': [[0, 4, '@disc:other:@raw', 0]]}
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); (root/'exe').mkdir()
                (root/'exe/SLUS_010.32.elf.map').write_text('.main 0x80090000 0x4\n'
                    ' .data.buffer 0x80090000 0x4 build/us/psx/gcc/src/main/main_bss_us.c.o\n')
                with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', '']), \
                     patch('dwpatch._iw', return_value=types.SimpleNamespace(Image=image)), \
                     patch('datacopy.find_sources', side_effect=find_sources):
                    result = delta_audit.inspect(payload, root, {'us': 'usa', 'eu': 'europe'}, {}, plan={})
            self.assertEqual(result['unavailable_bytes_by_base'], {'eu': 4} if changed else {})

    def test_zero_diff_witness_requires_real_equal_in_bounds_source(self):
        # Copy A/B, step outside the source, then seek back. A zero against the
        # implicit bspatch zero pad must never become a disc-source witness.
        delta = dict(source='EXE', diff=[2, 8], control=[[4, 1, -5], [4, 0, 0]])
        blob = b'xx' + bytes(8)
        target = b'AB\0\0!\0AB\0'
        spans = delta_audit.unchanged_witnesses(delta, blob, target, b'AB')
        self.assertEqual(spans, [[0, 2, 'EXE', 0], [6, 8, 'EXE', 0]])
        # A false source pin or mismatched target cannot certify a byte.
        self.assertEqual(delta_audit.unchanged_witnesses(
            dict(source='EXE', diff=[0, 2], control=[[2, 0, 0]]), bytes(2), b'XX', b'AB'), [])

    def test_nonzero_subtraction_is_measured_even_without_extras(self):
        delta = dict(diff=[0, 5], control=[[3, 2, 0], [2, 0, 0]])
        self.assertEqual(delta_audit.stored_information(delta, b'\0\x04\x05\x07\0', b'\x09\x04\x06xy\x07\0',
                         [[1, 5]]), dict(diff_bytes=3, nonzero_diff_bytes=3,
                                        nonzero_diff_equal_output=2, extra_bytes=2))

    def test_inspection_checks_linker_values_and_records_exact_copy_witness(self):
        target = bytes.fromhex('78563412')
        payload = dict(blob=bytes(4), deltas=[dict(file='SLUS_010.32', size=4,
            sha1=hashlib.sha1(target).hexdigest(), bases={'us': dict(source='BOOT',
                source_sha1=hashlib.sha1(target).hexdigest(), diff=[0, 4], extra=[4, 0], control=[[4, 0, 0]])})])
        def image(_):
            return types.SimpleNamespace(read=lambda _: target, f=io.BytesIO())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'exe').mkdir()
            linker = root / 'exe/SLUS_010.32.elf.map'
            for value, category in ((0x12345678, 'a'), (0x12345679, 'd')):
                linker.write_text(f'.main 0x80090000 0x4\n 0x80090000 0x4 LONG 0x{value:x} current_SIZE\n')
                with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', '']), \
                     patch('dwpatch._iw', return_value=types.SimpleNamespace(Image=image)), \
                     patch('datacopy.find_sources', return_value={'us': []}):
                    result = delta_audit.inspect(payload, root, {'us': 'player disc'}, {}, plan={})
                self.assertEqual(result['regions'][0]['category'], category)
                if category == 'd':
                    self.assertEqual(result['regions'][0]['bases']['us']['zero_diff_witnesses'],
                                     [[0, 4, 'BOOT', 0]])
                    self.assertEqual(result['unavailable_bytes_by_base'], {})
            # Wrong disc data is rejected before any zero difference is cleared.
            payload['deltas'][0]['bases']['eu'] = dict(payload['deltas'][0]['bases']['us'], source_sha1='bad pin')
            with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', '']), \
                 patch('dwpatch._iw', return_value=types.SimpleNamespace(Image=image)), \
                 patch('datacopy.find_sources', return_value={'us': [], 'eu': []}):
                with self.assertRaisesRegex(ValueError, 'source differs'):
                    delta_audit.inspect(payload, root, {'us': 'player disc', 'eu': 'wrong regional disc'}, {}, plan={})

    def test_unwitnessed_buffer_subtraction_still_blocks_publication(self):
        target = bytes([2]) * 16
        for source_byte in (0, 1):
            original = bytes([source_byte]) * 16
            payload = dict(blob=bytes([2 - source_byte]) * 16, deltas=[dict(file='SLUS_010.32', size=16,
                sha1=hashlib.sha1(target).hexdigest(), bases={'us': dict(source='BOOT',
                    source_sha1=hashlib.sha1(original).hexdigest(), diff=[0, 16], extra=[16, 0],
                    control=[[16, 0, 0]])})])
            def image(_):
                return types.SimpleNamespace(read=lambda _: original, f=io.BytesIO())
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); (root / 'exe').mkdir()
                (root / 'exe/SLUS_010.32.elf.map').write_text('.main 0x80090000 0x10\n'
                    ' .data.buffer 0x80090000 0x10 build/us/psx/gcc/src/main/main_bss_us.c.o\n')
                with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', '']), \
                     patch('dwpatch._iw', return_value=types.SimpleNamespace(Image=image)), \
                     patch('datacopy.find_sources', return_value={'us': []}):
                    result = delta_audit.inspect(payload, root, {'us': 'player disc'}, {}, plan={})
                self.assertEqual(result['unavailable_bytes_by_base'], {'us': 16})
                info = result['unavailable'][0]['stored_information']
                self.assertEqual(info['nonzero_diff_bytes'], 16)
                self.assertEqual(info['nonzero_diff_equal_output'], 16 if source_byte == 0 else 0)
                with self.assertRaises(literal_gate.GateFailure):
                    literal_gate.check([], {'sha1': {}}, [], root / 'gate.json', delta_audits={'test': result})

    def test_difference_similarity_tracks_moved_control_extents(self):
        delta = dict(diff=[0, 64], control=[[32, 8, 100], [32, 0, -4]])
        blob = bytes(32) + bytes(range(1, 33))
        self.assertEqual(delta_audit.region_similarity(delta, blob, 0, 32),
                         dict(diff_bytes=32, equal_bytes=32, extra_bytes=0, low_similarity=False))
        self.assertEqual(delta_audit.region_similarity(delta, blob, 32, 40),
                         dict(diff_bytes=32, equal_bytes=0, extra_bytes=8, low_similarity=True))

    def test_maps_follow_current_font_positions_and_language_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'exe').mkdir()
            (root / 'exe/SLUS_010.32.elf.map').write_text(
                '.main 0x80090000 0x1000\n'
                '                0x800901f0 0x4 LONG 0x12345678 main_TEXT_SIZE\n'
                ' .rodata.LATIN_GLYPH_BITS\n'
                '                0x80090200 0x40 build/us/psx/gcc/src/main/font.c.o\n'
                '.BTL 0x80010000 0x1000\n'
                ' .data.buffer 0x80010120 0x20 build/us/psx/gcc/src/btl/btl_bss_1.c.o\n')
            maps = delta_audit.sections(root, {'LANG_OVL': ['es:BTL_REL.BIN:ESBTL.BIN']})
            self.assertEqual(maps['SLUS_010.32'][0]['value'], 0x12345678)
            self.assertEqual(maps['SLUS_010.32'][1]['offset'], 0x200)
            self.assertEqual(maps['SCN/ESBTL.BIN'][0]['offset'], 0x120)

    def test_unavailable_encoded_data_blocks_even_with_no_literals(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(literal_gate, 'scan_chunks', return_value=[]):
            output = Path(temp) / 'gate.json'
            audits = {'everything': {'unavailable_bytes_by_base': {'eu': 128}, 'unavailable': []}}
            with self.assertRaisesRegex(literal_gate.GateFailure, '128 unverified reconstructed'):
                literal_gate.check([], {'sha1': {}}, [], output, delta_audits=audits)
            report = json.loads(output.read_text())
            self.assertEqual(report['literal_bytes'], 0)
            self.assertFalse(report['passed'])


if __name__ == '__main__':
    unittest.main()
