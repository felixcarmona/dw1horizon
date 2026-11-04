#!/usr/bin/env python3
"""The batch import's palette merge keeps every face's colours (import_batch.merge_palettes).

  tools/test_palette_merge.py
"""
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import import_batch  # noqa: E402


def ramp(r, g, b, n=15):
    return [0] + [(min(31, r * k // 15)) | (min(31, g * k // 15)) << 5 | (min(31, b * k // 15)) << 10 if k <= n else 0
                  for k in range(1, 16)]


HUES = [(31, 31, 31), (31, 0, 0), (0, 31, 0), (0, 0, 31), (0, 31, 31), (31, 0, 31), (16, 31, 0), (0, 31, 16),
        (0, 16, 31), (16, 0, 31), (31, 0, 16), (31, 16, 16), (16, 31, 16), (16, 16, 31), (31, 31, 16)]   # no two on one ray


def model(last, last_indices=15, first_indices=15):
    """16 palettes: 15 ramps of distinct hues used by four faces each and `last` used by one face; each face covers its
    own 16x16 block, whose texels run through indices 1..n (n = 15, or `first_indices` for palette 0's faces and
    `last_indices` for the last palette's face)."""
    pals = [ramp(*h, first_indices if k == 0 else 15) for k, h in enumerate(HUES)] + [last]
    idx = bytearray(256 * 128)
    prims = []
    for row in range(16):
        n = last_indices if row == 15 else first_indices if row == 0 else 15
        for k in range(1 if row == 15 else 4):
            u, v = (row * 16) % 256, k * 16
            for y in range(v, v + 16):
                for x in range(u, u + 16):
                    idx[y * 256 + x] = 1 + (x - u) * n // 16
            prims.append({'uvs': [(u, v), (u + 15, v), (u, v + 15), (u + 15, v + 15)], 'row': row})
    return types.SimpleNamespace(pals=pals, idx=idx, bones=[{'prims': prims}])


def colours(m):
    """The colour each covered texel shows through its face's palette."""
    out = {}
    for p in m.bones[0]['prims']:
        (u, v) = p['uvs'][0]
        for y in range(v, v + 16):
            for x in range(u, u + 16):
                out[(x, y)] = m.pals[p['row']][m.idx[y * 256 + x]]
    return out


def quiet(*a):
    pass


class Merge(unittest.TestCase):
    def test_near_copy_is_merged(self):
        m = model(ramp(31, 0, 1))
        self.assertEqual(import_batch.merge_palettes(m, 15, log=quiet), 1)
        self.assertEqual(len(m.pals), 15)

    def test_merge_re_indexes_texels_and_keeps_colours(self):
        # gold uses 3 colours, palette 0 only 8: the gold face's texels move into palette 0's free entries
        m = model(ramp(31, 22, 0, 3), last_indices=3, first_indices=8)
        before = colours(m)
        self.assertEqual(import_batch.merge_palettes(m, 15, log=quiet), 1)
        self.assertEqual(len(m.pals), 15)
        self.assertEqual(colours(m), before)

    def test_no_room_keeps_row_15(self):
        # gold uses 15 colours and every palette uses all of its entries: any merge repaints a face
        m = model(ramp(31, 22, 0))
        before = colours(m)
        lines = []
        self.assertEqual(import_batch.merge_palettes(m, 15, log=lines.append), 0)
        self.assertEqual(len(m.pals), 16)
        self.assertEqual(colours(m), before)
        self.assertIn('row 15 kept', lines[-1])


if __name__ == '__main__':
    unittest.main()
