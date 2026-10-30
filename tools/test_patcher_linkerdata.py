"""Address generation cannot carry non-pointer table fields or stale map words."""
import copy
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import codecopy
import dwpatch as dw
import linkerdata
import delta_audit


def elf_fixture():
    names = b'\0.shstrtab\0.main\0.symtab\0.bss\0.rel.main\0'
    main = struct.pack('<I', 0x80140008) + b'opaque field'
    symbols = bytes(16) + struct.pack('<IIIBBH', 0, 0x80140000, 0, 3, 0, 4)
    rel = struct.pack('<II', 0x80090000, (1 << 8) | 2)
    chunks = [names, main, symbols, rel]
    starts, cursor = [], 52
    for chunk in chunks:
        starts.append(cursor); cursor += len(chunk)
    header = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01' + bytes(9),
                         2, 8, 1, 0, 0, cursor, 0, 52, 0, 0, 40, 6, 1)
    def section(name, typ, flags, address, offset, size, link=0, info=0, stride=0):
        return struct.pack('<10I', names.index(name), typ, flags, address, offset, size, link, info, 4, stride)
    sections = [bytes(40), section(b'.shstrtab', 3, 0, 0, starts[0], len(names)),
                section(b'.main', 1, 2, 0x80090000, starts[1], len(main)),
                section(b'.symtab', 2, 0, 0, starts[2], len(symbols), stride=16),
                section(b'.bss', 8, 2, 0x80140000, 0, 64),
                section(b'.rel.main', 9, 0, 0, starts[3], len(rel), 3, 2, 8)]
    return header + b''.join(chunks) + b''.join(sections), main


class LinkerDataTests(unittest.TestCase):
    def test_sized_labels_come_from_the_current_elf_symbol_table(self):
        raw, _ = elf_fixture(); data = bytearray(raw)
        table = struct.unpack_from('<I', data, 32)[0]
        sym = table + 3*40
        symbol_offset = struct.unpack_from('<I', data, sym+16)[0]
        # Reuse the section-name string table as this small fixture's symbols.
        struct.pack_into('<I', data, sym+24, 1)
        struct.pack_into('<IIIBBH', data, symbol_offset+16, 11, 0x80090004, 8, 0x10, 0, 2)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'current.elf'; path.write_bytes(data)
            self.assertEqual(linkerdata.objects(path), {'.main': [(4, 8, '.main')]})
            # A label extending beyond its allocated output cannot authorize
            # generation or omit the bytes from the enclosing map object.
            struct.pack_into('<I', data, symbol_offset+16+8, 1000)
            path.write_bytes(data)
            self.assertEqual(linkerdata.objects(path), {})

    def test_current_relocation_and_map_bind_only_the_pointer_field(self):
        elf, main = elf_fixture()
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'exe'; folder.mkdir()
            path = folder / 'SLUS_010.32.elf'; path.write_bytes(elf)
            mapped = {'SLUS_010.32': [dict(offset=0, length=16, section='.data.struct', source='src/table.c')]}
            self.assertEqual(linkerdata.words(td, mapped, {'SLUS_010.32': main}, {}),
                             {'SLUS_010.32': [[0, '.bss', 0x80140000, 8]]})
            with self.assertRaisesRegex(ValueError, 'differs from target'):
                linkerdata.words(td, mapped, {'SLUS_010.32': bytes(16)}, {})
            mapped['SLUS_010.32'][0]['source'] = 'src/table_bss_us.c'
            self.assertEqual(linkerdata.words(td, mapped, {'SLUS_010.32': main}, {}), {})
            path.unlink()
            self.assertEqual(linkerdata.words(td, mapped, {'SLUS_010.32': main}, {}), {})

    def test_package_builder_discovers_addresses_without_an_override(self):
        elf, target = elf_fixture()
        original = bytes(len(target))
        image = types.SimpleNamespace(files={'SLUS_010.32': (0, len(original), False)}, read=lambda _: original)
        payload = dict(files={'SLUS_010.32': [['l', 0, len(target)]]},
                       blob=target, license=[], sources=[], code=[])
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'exe'; folder.mkdir()
            (folder / 'SLUS_010.32.elf').write_bytes(elf)
            (folder / 'SLUS_010.32.elf.map').write_text('.main 0x80090000 0x10\n'
                ' .data.table 0x80090000 0x10 build/us/psx/gcc/src/main/table.c.o\n')
            report = codecopy.copy_files(payload, td, {'SLUS_010.32': target}, {'us': image},
                                         plan={'authored': ['SLUS_010.32']})
        self.assertEqual(report['files'], ['SLUS_010.32'])
        entry = payload['deltas'][0]
        self.assertEqual(entry['linker_words'], [[0, '.bss', 0x80140000, 8]])
        self.assertEqual(dw.apply_binary_delta(entry, 'us', image.read, payload['blob']), target)

    def test_invalid_elf_cannot_authorize_a_pointer(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'bad.elf'
            for raw in (b'bad', bytes(100), elf_fixture()[0][:70]):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    linkerdata.relocations(path)

    def test_masked_record_requires_all_payload_fields_in_their_own_layout(self):
        target = b'ABCD' + bytes(4) + b'EFGH' + bytes(4) + b'IJKLMNOP'
        objects = [dict(offset=0, length=24, section='.data.record', source='src/record.c')]
        words = [[4, '.main', 0x80090000, 0], [12, '.main', 0x80090000, 8]]
        source = b'prefix' + b'ABCDxxxxEFGHyyyyIJKLMNOP' + b' suffix'
        self.assertEqual(linkerdata.payload_copies(objects, words, target, source),
                         [[0, 4, 6], [8, 4, 14], [16, 8, 22]])
        # Matching the individual numbers elsewhere is insufficient.
        self.assertEqual(linkerdata.payload_copies(objects, words, target,
                         b'ABCD__EFGH__IJKLMNOP'), [])
        # The anchor alone cannot witness a different field in this record.
        self.assertEqual(linkerdata.payload_copies(objects, words, target,
                         source.replace(b'EFGH', b'XXXX')), [])
        short = [dict(objects[0], length=16)]
        self.assertEqual(linkerdata.payload_copies(short, words, target, source), [])

    def test_builder_copies_short_fields_from_sized_record_inside_changed_assembly(self):
        # Neither eight-byte field can seed the scanner. Together they identify
        # a complete current-ELF record despite different surrounding SDK data.
        record = struct.pack('<5I', 73, 2, 0x80090008, 0, 91 << 16)
        target = b'new head' + record + b'new tail'
        member = dict(offset=8, length=20, section='.data.sdk.record', source='asm/data/sdk')
        obj = dict(offset=0, length=len(target), section='.data.sdk', source='asm/data/sdk',
                   members=[member, dict(member)])  # ELF aliases must not overlap.
        words = [[16, '.main', 0x80090000, 8]]
        originals = {base: b'old SDK prefix' + record[:8] + struct.pack('<I', pointer)
                     + record[12:] + b'old SDK suffix'
                     for base, pointer in [('us', 0x800A0010), ('eu', 0x800B0020)]}
        images = {base: types.SimpleNamespace(files={'SLUS_010.32': (0, len(old), False),
                      'SCN/TEST_REL.BIN': (0, len(old), False)}, read=lambda _, old=old: old)
                  for base, old in originals.items()}
        file = 'SCN/TEST_REL.BIN'
        payload = dict(files={file: [['l', 0, len(target)]]}, blob=target,
                       license=[], sources=[], code=[])
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'exe'; folder.mkdir()
            (folder / 'SLUS_010.32.elf.map').touch()
            with patch.object(delta_audit, 'sections', return_value={file: [obj]}), \
                 patch.object(linkerdata, 'words', return_value={file: words}), \
                 patch.object(codecopy, 'make_delta', side_effect=lambda old, new:
                     ([[len(new), 0, 0]], bytes((a-b) & 255 for a,b in zip(new, old)), b'')):
                # An ordinary delta producer may subtract from the wrong
                # layout; exact record discovery must repair that choice.
                codecopy.copy_files(payload, td, {file: target}, images, plan={})
        entry = payload['deltas'][0]
        for base, old in originals.items():
            self.assertEqual(dw.apply_binary_delta(entry, base, images[base].read, payload['blob']), target)
            witnesses = delta_audit.unchanged_witnesses(entry['bases'][base], payload['blob'], target, old)
            for a, n in [(8, 8), (20, 8)]:
                self.assertTrue(any(lo <= a and a+n <= hi for lo, hi, _, _ in witnesses))
            self.assertEqual(linkerdata.payload_copies([obj], words, target, old),
                             [[8, 8, 14], [20, 8, 26]])
            # Separate matching fragments and one changed record field cannot
            # authorize short copies. Relocated pointers alone prove nothing.
            bad = old.replace(record[12:], b'X' * 8) + record[12:]
            self.assertEqual(linkerdata.payload_copies([obj], words, target, bad), [])

    def check_rewrite(self, old, target, controls, diff, extra, offset):
        words = [[offset, '.main', 0x80090000, 8]]
        control, diff, extra = codecopy.generate_linker_words(controls, diff, extra, len(old), words)
        d = dict(source='BOOT', source_sha1=hashlib.sha1(old).hexdigest(),
                 control=control, diff=[0, len(diff)], extra=[len(diff), len(extra)])
        entry = dict(size=len(target), sha1=hashlib.sha1(target).hexdigest(),
                     bases={'us': d}, linker_words=words)
        blob = diff + extra
        self.assertEqual(dw.apply_binary_delta(entry, 'us', lambda _: old, blob), target)
        return entry, blob

    def test_word_crossing_diff_extra_and_seek_keeps_nonpointer_payload(self):
        old = b'abcdef'
        target = b'xyz' + struct.pack('<I', 0x80090008) + b'12'
        diff = bytes((a - b) & 255 for a, b in zip(target[:4], old[:4]))
        diff += bytes((a - b) & 255 for a, b in zip(target[6:], old[1:4]))
        self.check_rewrite(old, target, [[4, 2, -3], [3, 0, 0]], diff, target[4:6], 3)

    def test_original_out_of_bounds_padding_cannot_read_generated_tail(self):
        target = b'ab12' + struct.pack('<I', 0x80090008) + b'XY'
        self.check_rewrite(b'ab', target, [[10, 0, 0]], bytes(2) + target[2:], b'', 4)

    def test_declared_but_unused_or_nonzero_expression_is_rejected(self):
        target = struct.pack('<I', 0x80090008)
        entry, blob = self.check_rewrite(bytes(4), target, [[4, 0, 0]], target, b'', 0)
        for mutation in ('nonzero', 'real-source', 'wrong-target'):
            bad = copy.deepcopy(entry); data = bytearray(blob)
            if mutation == 'nonzero':
                data[0] = 1
            elif mutation == 'real-source':
                bad['bases']['us']['control'][0][2] = 0
            else:
                bad['linker_words'][0][0] = 1
            with self.subTest(mutation=mutation), self.assertRaises(dw.PatchError):
                dw.apply_binary_delta(bad, 'us', lambda _: bytes(4), data)

    def test_generated_pointer_never_clears_adjacent_nonpointer_fields(self):
        elf, target = elf_fixture()
        old = bytes(len(target))
        words = [[0, '.bss', 0x80140000, 8]]
        control, diff, extra = codecopy.generate_linker_words([[16, 0, 0]], target, b'', 16, words)
        entry = dict(file='SLUS_010.32', size=16, sha1=hashlib.sha1(target).hexdigest(), linker_words=words,
                     bases={'us': dict(source='BOOT', source_sha1=hashlib.sha1(old).hexdigest(),
                                       control=control, diff=[0, len(diff)], extra=[len(diff), len(extra)])})
        payload = dict(deltas=[entry], blob=diff + extra)
        image = lambda _: types.SimpleNamespace(read=lambda _: old, f=io.BytesIO())
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / 'exe'; folder.mkdir()
            (folder / 'SLUS_010.32.elf').write_bytes(elf)
            (folder / 'SLUS_010.32.elf.map').write_text('.main 0x80090000 0x10\n'
                ' .data.table 0x80090000 0x10 build/us/psx/gcc/src/main/table.c.o\n')
            with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', 'table']), \
                 patch.object(dw, '_iw', return_value=types.SimpleNamespace(Image=image)), \
                 patch('datacopy.find_sources', return_value={'us': []}):
                result = delta_audit.inspect(payload, td, {'us': 'disc'}, {}, {})
            self.assertEqual(result['unavailable_bytes_by_base'], {'us': 12})
            self.assertEqual(result['unavailable'][0]['unverified_ranges'], [[4, 12]])
            (folder / 'SLUS_010.32.elf').unlink()
            with patch.object(delta_audit.subprocess, 'check_output', side_effect=['pin', 'table']), \
                 patch.object(dw, '_iw', return_value=types.SimpleNamespace(Image=image)):
                with self.assertRaisesRegex(ValueError, 'lacks current ELF'):
                    delta_audit.inspect(payload, td, {'us': 'disc'}, {}, {})


if __name__ == '__main__':
    unittest.main()
