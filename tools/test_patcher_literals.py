#!/usr/bin/env python3
"""Audit search and literal inventories must not miss alignment/sector edges."""
import hashlib
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import literal_audit as audit


class LiteralInventoryTests(unittest.TestCase):
    def test_inventory_tracks_copy_lengths_and_license(self):
        p = dict(files={'CODE': [['c', 0, 9, 3], ['r', 0], ['l', 0, 20], ['o', 'EARLY', 0, 5]]},
                 code=[[0, 12, 17]], blob=b'x' * 20 + b'yz', license=[['l', 20, 2]])
        rows = audit.literal_runs(p)
        self.assertEqual([(r['file'], r['offset'], r['length'], r['operation']) for r in rows],
                         [('CODE', 20, 20, 2), ('license_data.dat', 0, 2, 0)])
        self.assertEqual(rows[0]['sha1'], hashlib.sha1(b'x' * 20).hexdigest())

    def test_mapping_literals_are_separate_and_verified(self):
        import json
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'bases').mkdir(); (root/'evidence').mkdir()
            mapping = {'files': {'ART': {'ops': [{'copy': [0, 2]}, {'data': '3233'},
                                                 {'fill': [0, 2]}, {'data': 'ff'}]}}}
            (root/'bases/base.json').write_text(json.dumps(mapping))
            image = SimpleNamespace(read=lambda q: b'0123456789', f=SimpleNamespace(close=lambda: None))
            with patch.object(audit.iw, 'Image', return_value=image):
                totals = audit.mapping_literals(root, root/'evidence', {'images': ['USA']}, {'us': 0})
            self.assertEqual(totals['data_bytes'], 3)
            self.assertEqual(totals['class_c'], 2)
            self.assertEqual(totals['class_d'], 1)
            rows = json.loads((root/'evidence/mapping-literals.json').read_text())
            self.assertEqual([(r['offset'],r['opcode'],r['category'])for r in rows],
                             [(2,'data','c'),(4,'fill','a'),(6,'data','d')])

    def test_overlapping_seeds_cover_a_short_tail(self):
        data = bytes(range(17))
        with patch.object(audit, 'DiscFiles') as reader:
            reader.return_value.read.side_effect = lambda row: data[:16] if row == 0 else data[1:]
            spans = audit.extend_matches(data, [dict(blob_offset=0, length=17)],
                                         {0: (0, 0), 1: (1, 0)}, {})
        self.assertEqual(spans, [[0, 16, 0, 0], [16, 17, 1, 15]])

    def test_extending_matches_checks_seeds(self):
        with patch.object(audit, 'DiscFiles') as reader:
            reader.return_value.read.return_value = b'wrong source data'
            with self.assertRaises(ValueError):
                audit.extend_matches(bytes(16), [dict(blob_offset=0, length=16)], {0: (0, 0)}, {})


@unittest.skipUnless(shutil.which('c++'), 'developer scan needs a C++17 compiler')
class LiteralSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='test-literal-scan-')
        cls.root = Path(cls.temp.name)
        cls.exe = cls.root / 'scan'
        source = Path(audit.__file__).with_name('literal_scan.cpp')
        subprocess.run(['c++', '-O2', '-std=c++17', str(source), '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unindexed_user_data_crosses_sector_headers(self):
        logical = random.Random(21).randbytes(4096)
        raw = bytearray(2352 * 2)
        raw[24:24+2048] = logical[:2048]
        raw[2352+24:2352+24+2048] = logical[2048:]
        disc = self.root / 'hidden archive.bin'; disc.write_bytes(raw)
        target = logical[2040:2081]
        (self.root/'blob').write_bytes(target)
        (self.root/'ranges').write_text('0 41\n')
        (self.root/'sources').write_text(f'{disc}\t0\t0\t0\t3\n')
        result = subprocess.run([str(self.exe), str(self.root/'blob'), str(self.root/'ranges'),
                                 str(self.root/'sources')], capture_output=True, text=True, check=True)
        hits = [tuple(map(int, line.split())) for line in result.stdout.splitlines()]
        self.assertEqual({q for q, _, _ in hits}, set(range(26)))
        for q, row, off in hits:
            self.assertEqual(row, 0)
            self.assertEqual(logical[off:off+16], target[q:q+16])
        with disc.open('rb') as file:
            view = audit.UserData(file)
            self.assertEqual(view[2040:2081], target)
            self.assertEqual(view[2048], logical[2048])

    def test_all_offsets_raw_bytes_and_sector_crossings(self):
        rng = random.Random(192)
        logical = bytearray(rng.randbytes(3500))
        logical[115:285] = bytes(170)
        raw = bytearray(rng.randbytes(2352 * 2))
        for off in range(0, len(logical), 2048):
            part = logical[off:off+2048]
            raw[(off//2048)*2352+24:(off//2048)*2352+24+len(part)] = part
        disc = self.root / 'disc with spaces.bin'; disc.write_bytes(raw)
        parts = [bytes(logical[2040:2081]), bytes(128), bytes(raw[0:23]), rng.randbytes(37),
                 bytes(logical[300:331]), bytes(logical[331:347])]
        blob = b''.join(parts); (self.root / 'blob').write_bytes(blob)
        off = 0; ranges = []
        for part in parts:
            ranges.append((off, len(part))); off += len(part)
        (self.root / 'ranges').write_text(''.join(f'{a}\t{n}\n' for a, n in ranges))
        (self.root / 'sources').write_text(f'{disc}\t0\t0\t3500\t0\n{disc}\t1\t0\t0\t2\n')
        result = subprocess.run([str(self.exe), str(self.root/'blob'), str(self.root/'ranges'),
                                 str(self.root/'sources')], capture_output=True, text=True, check=True)
        found = {}
        data = [bytes(logical), bytes(raw)]
        for line in result.stdout.splitlines():
            q, row, pos = map(int, line.split())
            self.assertNotIn(q, found)
            found[q] = (row, pos)
            self.assertEqual(blob[q:q+16], data[row][pos:pos+16])
        expected = {q for a,n in ranges for q in range(a, a+n-15)
                    if any(blob[q:q+16] in source for source in data)}
        self.assertEqual(set(found), expected)
        self.assertEqual(found[0][0], 0)  # first match spans two logical user-data sectors
        # Uniform seeds choose the longest run, avoiding thousands of tiny zero-copy recipes.
        row, pos = found[len(parts[0])]
        self.assertEqual(data[row][pos:pos+128], bytes(128))


if __name__ == '__main__':
    unittest.main()
