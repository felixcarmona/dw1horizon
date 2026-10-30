#!/usr/bin/env python3
"""Relocated code and output copies must reconstruct the target before the disc writer sees it.

Run with python3 tools/test_patcher_reloc.py (standard library only; no game files).
"""
import hashlib
import io
from pathlib import Path
import random
import struct
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import dwpatch as dw
import reloc


class Image:
    def __init__(self, files):
        self.data = files
        self.files = {q: (0, len(b), False) for q, b in files.items()}

    def read(self, q):
        return self.data[q]


class Encoder:
    def __init__(self, usa, base):
        self.sources = ['SLUS_010.32']
        self.code = [[0, 0, len(usa)]]
        self.bases = {'eu': Image({'SLES_029.14': base})}
        self.mappings = {'eu': {'boot': 'SLES_029.14'}}
        self.pool = dw.Pool([('SLUS_010.32', usa)])
        self.universal = []
        self.blob = bytearray()
        self.data = lambda q: usa

    def lit(self, b):
        op = ['l', len(self.blob), len(b)]
        self.blob.extend(b)
        return op


def words(*xs):
    return struct.pack(f'<{len(xs)}I', *xs)


class RelocationTests(unittest.TestCase):
    def test_relocated_calls_globals_and_pointer_table(self):
        rng = random.Random(13)
        left = rng.randbytes(64)
        right = rng.randbytes(64)
        # jal, lui, addiu, lw, and a RAM pointer move; a changed branch must stay literal.
        us = left + words(0x0c024800, 0x3c028014, 0x24421800, 0x8c431804, 0x80141800,
                          0x10430003) + right
        eu = left + words(0x0c024900, 0x3c028015, 0x24421900, 0x8c431904, 0x80151900,
                          0x10430004) + right
        enc = Encoder(us, b'PREFIX!!' + eu)
        # Every supported non-USA base has its own boot-file mapping and copy table.
        for key in ('fr', 'de', 'es', 'it', 'jp1'):
            boot = dw.BASES[key]['boot']
            enc.bases[key] = Image({boot: b'PREFIX!!' + eu})
            enc.mappings[key] = {'boot': boot}
        files = {'CODE': [['r', 0]], 'SPANISH': [['l', 0, len(us)]]}
        enc.blob.extend(us)
        reused = reloc.reuse_outputs(enc, files, {'CODE': us, 'SPANISH': us},
                                     {'CODE', 'SPANISH'}, {'CODE', 'SPANISH'}, dw.Pool)
        self.assertEqual(reused, len(us))
        tables, fix, lost = reloc.relocate(enc, files, dw.Pool, say=lambda s: None)
        self.assertTrue(fix['eu'])
        self.assertLess(lost, 8)
        reloc.compact(enc, files)
        self.assertTrue(any(op[0] == 'o' for op in files['SPANISH']))
        payload = dict(sources=enc.sources, code=enc.code, reloc=tables, fix=fix,
                       files=files, blob=bytes(enc.blob), layout='', license=[],
                       sha1={q: hashlib.sha1(us).hexdigest() for q in files})
        # Exercise the actual apply assembler, including its SHA-1 checks; replace only the disc writer.
        writer = types.SimpleNamespace(Layout=lambda x: x,
                                       write=lambda lay, got, out, **kw: (None, dict(got)))
        for key in dw.BASES:
            base = types.SimpleNamespace(key=key, map=enc.mappings.get(key),
                                         data=lambda q, cache=False: us,
                                         code=lambda q: b'PREFIX!!' + eu)
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(got, {'CODE': us, 'SPANISH': us})
        payload['fix'] = {}
        with patch.object(dw, '_iw', return_value=writer), self.assertRaises(dw.PatchError):
            dw.build_disc3(payload, base, {}, 'unused', progress=False)

    def test_audited_literals_copy_each_bases_own_files(self):
        data = bytes(range(80))
        p = dict(sources=[], code=[], reloc={'eu': {}}, fix={},
                 files={'CODE': [['l', 0, 80]]}, license=[], blob=data,
                 sha1={'CODE': hashlib.sha1(data).hexdigest()}, layout='')
        matches = {'us': [(10, 70, 'US', 2)], 'eu': [(20, 60, 'EU', 5)]}
        self.assertEqual(reloc.copy_literal_sources(p, matches), 40)
        writer = types.SimpleNamespace(Layout=lambda x: x,
                                       write=lambda lay, got, out, **kw: (None, dict(got)))
        for key in ('us', 'eu'):
            base = types.SimpleNamespace(key=key, map=None if key == 'us' else {},
                data=lambda q, cache=False: b'xx' + data[10:70],
                code=lambda q: b'xxxxx' + data[20:60])
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(p, base, {}, 'unused', progress=False)
            self.assertEqual(got['CODE'], data)
        self.assertEqual(len(p['blob']), 40)

    def test_literal_copies_need_all_bases_and_ordered_spans(self):
        p = dict(blob=bytes(80), reloc={'eu': {}, 'jp1': {}})
        with self.assertRaises(ValueError):
            reloc.copy_literal_sources(p, {'us': [], 'eu': []})
        with self.assertRaises(ValueError):
            reloc.copy_literal_sources(p, {'us': [(20, 40, 'US', 0), (10, 30, 'US', 0)],
                                          'eu': [], 'jp1': []})

    def test_raw_copy_reads_only_the_verified_range(self):
        data = random.Random(192).randbytes(80)
        payload = dict(sources=['@raw'], code=[[0, 7, 20]], blob=b'', layout='',
                       files={'CODE': [['r', 0]]}, license=[], fix={},
                       reloc={'eu': {'0': [['@raw', 11, 20]]}},
                       sha1={'CODE': hashlib.sha1(data[7:27]).hexdigest()})
        writer = types.SimpleNamespace(Layout=lambda x: x,
                                       write=lambda lay, got, out, **kw: (None, dict(got)))
        for key, raw in [('us', data), ('eu', b'xxxx' + data)]:
            base = types.SimpleNamespace(key=key, map=None if key=='us' else {},
                                         img=types.SimpleNamespace(f=io.BytesIO(raw)))
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
            self.assertEqual(got['CODE'], data[7:27])

    def test_user_data_copy_spans_raw_sector_headers(self):
        logical = random.Random(81).randbytes(4096)
        raw = bytearray(2352 * 2)
        raw[24:24+2048] = logical[:2048]
        raw[2352+24:2352+24+2048] = logical[2048:]
        data = logical[2040:2060]
        payload = dict(sources=['@userdata'], code=[[0, 2040, 20]], blob=b'', layout='',
                       files={'CODE': [['r', 0]]}, license=[], fix={}, reloc={},
                       sha1={'CODE': hashlib.sha1(data).hexdigest()})
        base = types.SimpleNamespace(key='us', map=None, img=types.SimpleNamespace(f=io.BytesIO(raw)))
        writer = types.SimpleNamespace(Layout=lambda x: x,
                                       write=lambda lay, got, out, **kw: (None, dict(got)))
        with patch.object(dw, '_iw', return_value=writer):
            got, _ = dw.build_disc3(payload, base, {}, 'unused', progress=False)
        self.assertEqual(got['CODE'], data)

    def test_instruction_changes_are_not_address_fixups(self):
        self.assertIsNone(reloc.addr_xor(0x10430003, 0x10430004))  # relative branch
        self.assertIsNone(reloc.addr_xor(0x24421800, 0x24621800))  # different register
        self.assertIsNone(reloc.addr_xor(0x00431021, 0x00431023))  # different ALU op
        self.assertIsNone(reloc.addr_xor(0x80141800, 0x01041800))  # not two RAM pointers

    def test_output_copy_never_uses_future_files(self):
        data = random.Random(17).randbytes(100)
        enc = types.SimpleNamespace(blob=bytearray(data * 2), usa_lit={0, 100})
        files = {'FIRST': [['l', 0, 100]], 'SECOND': [['l', 100, 100]]}
        reloc.reuse_outputs(enc, files, dict.fromkeys(files, data), set(files), set(files), dw.Pool)
        self.assertEqual(files['FIRST'], [['l', 0, 100]])
        self.assertEqual(files['SECOND'], [['o', 'FIRST', 0, 100]])
        self.assertEqual(reloc.compact(enc, files), {'FIRST': 100})
        self.assertEqual(enc.blob, data)

    def test_output_copy_splits_code_and_literal_operations(self):
        data = random.Random(21).randbytes(100)
        enc = Encoder(b'xx' + data + b'yy', b'xx' + data + b'yy')
        enc.blob.extend(b'xx' + data + b'yy')
        files = {'EARLY': [['l', 2, 100]], 'LATER': [['r', 0]]}
        reloc.reuse_outputs(enc, files, {'EARLY': data, 'LATER': b'xx' + data + b'yy'},
                            {'EARLY', 'LATER'}, set(files), dw.Pool)
        self.assertEqual(files['LATER'][1], ['o', 'EARLY', 0, 100])
        self.assertEqual(enc.code, [[0, 0, 2], [0, 102, 2]])
        self.assertEqual(files['LATER'][0], ['r', 0])
        self.assertEqual(files['LATER'][2], ['r', 1])


if __name__ == '__main__':
    unittest.main()
