#!/usr/bin/env python3
"""tools/models/audit_textures.py finds the faces that sample a texture wrongly, and nothing else.

  tools/test_audit_textures.py

A synthetic 4 bpp texture with a copy of its palette stored inside the image (as Digital Card Battle's TIMs do) and
one face per finding; then, when extracted/ is present, the disc's own species, which must have no error.
"""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools' / 'models'), str(ROOT)]
import audit_textures as A  # noqa: E402
import mmd  # noqa: E402

GREY = [0] + [(k << 10) | (k << 5) | k for k in range(1, 16)]          # a smooth ramp, colour 0 transparent
NOISY = [0] + [0x7FFF if k % 2 else 0x001F for k in range(1, 16)]       # neighbouring indices far apart


def tim(rows, paint):
    """An ALLTIM-style entry: 16 x len(rows) CLUT, 256 x 128 image; paint(idx) fills the indices."""
    clut = struct.pack('<IHHHH', 12 + 32 * len(rows), 0, 0, 16, len(rows)) + b''.join(struct.pack('<16H', *r) for r in rows)
    idx = bytearray(256 * 128)
    paint(idx)
    pix = bytes(idx[i] | idx[i + 1] << 4 for i in range(0, len(idx), 2))
    return struct.pack('<II', 0x10, 8) + clut + struct.pack('<IHHHH', 12 + len(pix), 0, 0, 64, 128) + pix


def face(uv, row, mode=0x34):
    return mmd.Prim.encode(dict(mode=mode, flag=0, uv=uv, cba=(A.CLUT_BASE + row) << 6, tsb=5, norms=[0, 0, 0],
                                verts=[0, 1, 2]))


def model(*prims):
    t = mmd.TMD()
    ob = mmd.TMDObject()
    ob.prims = list(prims)
    t.objects = [ob]
    return t


def paint(idx):
    for y in range(0, 32):                       # a ramp: indices 1..15 across x, the art faces sample
        for x in range(0, 64):
            idx[y * 256 + x] = 1 + x * 15 // 64
    for y in range(32, 48):                      # a cut-out: colour 0 everywhere
        for x in range(0, 64):
            idx[y * 256 + x] = 0
    for y in range(48, 80):                      # a fine dither of indices 1 and 2: smooth through GREY, noise through NOISY
        for x in range(0, 64):
            idx[y * 256 + x] = 1 + (x + y) % 2
    for k, word in enumerate(GREY):              # palette row 0 stored in the image at (192, 112), 4 texels a word
        for n in range(4):
            idx[112 * 256 + 192 + 4 * k + n] = (word >> (4 * n)) & 15


def findings(prim, rows=None):
    t = mmd.Tim4(tim(rows or [GREY, NOISY, [0] * 16], paint))
    (f,) = A.audit(model(prim), t)
    return {k for k, _ in f['find']}


class Faces(unittest.TestCase):
    def test_clean_face(self):
        self.assertEqual(findings(face([(0, 0), (60, 0), (0, 30)], 0)), set())

    def test_face_on_the_stored_palette(self):
        self.assertIn('clut-area', findings(face([(192, 112), (250, 112), (192, 113)], 0)))
        self.assertIn('clut-area', A.ERRORS)

    def test_row_past_the_texture(self):
        self.assertEqual(findings(face([(0, 0), (60, 0), (0, 30)], 5)), {'row'})

    def test_empty_row_over_art(self):
        self.assertEqual(findings(face([(0, 0), (60, 0), (0, 30)], 2)), {'empty-row'})

    def test_empty_row_placeholder(self):
        self.assertEqual(findings(face([(0, 33), (60, 33), (0, 46)], 2)), {'invisible'})

    def test_below_the_image(self):
        self.assertIn('outside', findings(face([(0, 120), (60, 120), (0, 140)], 0)))

    def test_cut_out_face(self):
        self.assertEqual(findings(face([(0, 33), (60, 33), (0, 46)], 0)), {'invisible'})
        self.assertEqual(findings(face([(0, 33), (60, 33), (0, 46)], 0, mode=0x36)), {'holes'})   # semi-transparent

    def test_wrong_row_shows_as_noise(self):
        self.assertEqual(findings(face([(0, 50), (60, 50), (0, 78)], 0)), set())
        self.assertEqual(findings(face([(0, 50), (60, 50), (0, 78)], 1)), {'noise'})


@unittest.skipUnless((ROOT / 'extracted' / 'CHDAT' / 'ALLTIM.TIM').exists(), 'needs extracted/')
class Originals(unittest.TestCase):
    def test_no_error_on_the_disc(self):
        report = A.run(A.original_models({0, 3, 31, 52, 85, 129, 177}))
        self.assertEqual({t: r['summary'] for t, r in report.items() if r.get('errors') or 'error' in r}, {})


if __name__ == '__main__':
    unittest.main()
