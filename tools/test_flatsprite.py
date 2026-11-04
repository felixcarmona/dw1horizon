#!/usr/bin/env python3
"""tools/flatsprite.py gives every texture the frames a flattened Digimon is drawn with, where the model leaves room.

  tools/test_flatsprite.py

Asset-free: the span rasteriser against tools/models/audit_textures.py's, the two-colour recolouring, the placement
on synthetic texel maps. With extracted/: Agumon's model and texture (its own frames are kept), the same texture
without them, with a face over the originals' corner, with a face in row 15, with islands over the whole page (moved,
every face reading what it read); Cherrymon's small texture completed; the disc's own species.
"""
from pathlib import Path
import random
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import flatsprite as F  # noqa: E402
from models import audit_textures as A  # noqa: E402

EXTRACTED = (ROOT / 'extracted' / 'CHDAT' / 'ALLTIM.TIM').exists()


def icon(colours=(0x0421, 0x7FFF, 0x001F)):
    """A 0x220-byte icon: frame k has index 1 on its border, 2 inside, index 0 in the corner texel."""
    pal = [0] + list(colours) + [0] * (15 - len(colours))
    img = [[0] * 32 for _ in range(32)]
    for f in range(4):
        ox, oy = (f & 1) * 16, (f >> 1) * 16
        for y in range(1, 15):
            for x in range(1, 15):
                img[oy + y][ox + x] = 1 if x in (1, 14) or y in (1, 14) else 2 + (f == 3)
    return struct.pack('<16H', *pal) + bytes(img[y][x] | img[y][x + 1] << 4 for y in range(32) for x in range(0, 32, 2))


class Pure(unittest.TestCase):
    def test_spans_match_the_audit(self):
        rnd = random.Random(7)
        for _ in range(3000):
            n = rnd.choice((3, 4))
            k = rnd.choice((6, 40, 200))
            uv = [(rnd.randint(0, k), rnd.randint(0, min(k, 127))) for _ in range(n)]
            self.assertEqual(F.texels(uv), A.texels(uv, 256, 256), uv)

    def test_mono_keeps_two_colours(self):
        out = F.mono(icon((0x0421, 0x7FFF, 0x2108, 0x6318)))
        pal = struct.unpack_from('<16H', out, 0)
        self.assertEqual(pal[:5], (0, F.OUTLINE, F.FILL, F.OUTLINE, F.FILL))
        self.assertEqual(out[32:], icon((0x0421, 0x7FFF, 0x2108, 0x6318))[32:])

    def test_place_prefers_the_originals_corner(self):
        free = F.Use([])
        self.assertEqual(F.place((free, free)), F.NATIVE)

    def test_place_moves_to_a_free_block(self):
        marks = [(x, y) for x in range(256) for y in range(128) if not (10 <= x < 50 and 20 <= y < 60)]
        cells = F.place((F.Use(marks), F.Use(marks, 0)))
        self.assertEqual(len(set(cells)), 4)
        for u, v in cells:
            self.assertTrue(11 <= u and u + F.CELL <= 49 and 21 <= v and v + F.CELL <= 59, cells)

    def test_place_shares_cells_when_short(self):
        holes = [(5, 5), (100, 70)]       # two 17x17 holes only: a 15x15 cell and its margin each
        marks = [(x, y) for x in range(256) for y in range(128)
                 if not any(hx <= x < hx + 17 and hy <= y < hy + 17 for hx, hy in holes)]
        cells = F.place((F.Use(marks), F.Use(marks, 0)))
        self.assertEqual(sorted(set(cells)), sorted((x + 1, y + 1) for x, y in holes))
        self.assertEqual(cells[0], cells[2])                    # attack shares idle's cell
        with self.assertRaises(F.NoRoom):
            full = [(x, y) for x in range(256) for y in range(128)]
            F.place((F.Use(full), F.Use(full, 0)))

    def test_shared_row_picks_contrast_with_a_transparent_entry(self):
        rows = [[0x1111] * 16 for _ in range(16)]
        rows[3] = [0x2222, 0, 0x0421, 0x7FFF] + [0x4210] * 12
        rows[5] = [0, 0x2108, 0x4210] + [0x3000] * 13
        self.assertEqual(F.shared_row(rows), (3, 1, 2, 3))


@unittest.skipUnless(EXTRACTED, 'needs extracted/')
class Agumon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mmd
        import species
        cls.mmd = mmd
        cls.model = Path(species.originals().model_path(3)).read_bytes()
        cls.tex = mmd.alltim_entry(Path(species.ALLTIM).read_bytes(), 3)
        cls.nb = len(species.originals().rec[3]['bones'])

    def without_frames(self, clear=None):
        """Agumon's texture with an empty row 15 (clear: (row, index) of an entry made transparent)."""
        rows, cx, cy, idx, px, py, _ = F.parse_tim(self.tex)
        rows[F.ROW] = [0] * 16
        if clear:
            rows[clear[0]][clear[1]] = 0
        return F.build_tim(rows, cx, cy, idx, px, py).ljust(F.TEX_SIZE, b'\0')

    def with_faces(self, faces, keep=True):
        """Agumon's model with more textured triangles in object 0 ((uv, row) each); keep=False: only those."""
        m = self.mmd.MMD.parse(self.model, self.nb)
        if not keep:
            for ob in m.tmd.objects:
                ob.prims = [p for p in ob.prims if not p.mode & 4]
        m.tmd.objects[0].prims += [self.mmd.Prim.encode(dict(
            mode=0x34, flag=0, uv=uv, cba=(A.CLUT_BASE + row) << 6, tsb=5, norms=[0, 0, 0], verts=[0, 1, 2]))
            for uv, row in faces]
        return m.build()

    def same_texels(self, model, tex, new_model, new_tex):
        """Every face of the new model reads, through its row and with a texel of margin, what it read before."""
        ro, io = F.parse_tim(tex)[0], F.parse_tim(tex)[3]
        rn, inn = F.parse_tim(new_tex)[0], F.parse_tim(new_tex)[3]
        for (_, p1), (_, p2) in zip(F.prims_at(model), F.prims_at(new_model)):
            if not p1.mode & 4:
                continue
            d1, d2 = p1.decode(), p2.decode()
            dx, dy = d2['uv'][0][0] - d1['uv'][0][0], d2['uv'][0][1] - d1['uv'][0][1]
            self.assertEqual([(u + dx, v + dy) for u, v in d1['uv']], d2['uv'])
            r = A.row_of(d1['cba'])
            for x, y in F.texels(d1['uv']):
                for X, Y in ((x + ex, y + ey) for ex in (-1, 0, 1) for ey in (-1, 0, 1)):
                    if 0 <= X < 256 and 0 <= Y < 128 and 0 <= X + dx < 256 and 0 <= Y + dy < 128:
                        self.assertEqual(ro[r][io[Y * 256 + X]], rn[r][inn[(Y + dy) * 256 + X + dx]])

    def test_own_frames_kept(self):
        out, model, cells, row, how = F.stamp(self.tex, self.model, self.nb, F.mono(icon()))
        self.assertEqual((cells, row, how, model), (F.NATIVE, F.ROW, 'its own', self.model))
        self.assertEqual(F.frames_of(out), F.frames_of(self.tex))
        self.assertEqual(F.trailer(out), (F.NATIVE, F.ROW))
        self.assertEqual(F.check(out, self.model, self.nb), [])
        self.assertEqual(len(out), F.TEX_SIZE)

    def test_missing_frames_drawn_in_the_corner(self):
        tex = self.without_frames()
        self.assertTrue(F.check(tex))
        out, _, cells, row, how = F.stamp(tex, self.model, self.nb, F.mono(icon()))
        self.assertEqual((cells, row, how), (F.NATIVE, F.ROW, 'row 15'))
        self.assertEqual(F.check(out, self.model, self.nb), [])
        self.assertEqual(F.parse_tim(out)[0][F.ROW][:3], [0, F.OUTLINE, F.FILL])

    def test_corner_taken_moves_the_frames(self):
        model = self.with_faces([([(200, 80), (255, 80), (200, 127)], 0)])
        out, same, cells, row, how = F.stamp(self.without_frames(), model, self.nb, F.mono(icon()))
        self.assertNotEqual(cells, F.NATIVE)
        self.assertEqual((row, how, same), (F.ROW, 'row 15, moved', model))
        self.assertEqual(F.check(out, model, self.nb), [])
        self.assertEqual(F.trailer(out), (cells, F.ROW))
        self.same_texels(model, self.tex, model, out)

    def test_row_15_in_use_draws_in_a_shared_row(self):
        model = self.with_faces([([(200, 80), (255, 80), (200, 127)], 15)])
        with self.assertRaises(F.NoRoom):                     # no other row of Agumon has a transparent entry
            F.stamp(self.without_frames(), model, self.nb, F.mono(icon()))
        out, _, cells, row, how = F.stamp(self.without_frames((2, 15)), model, self.nb, F.mono(icon()))
        self.assertEqual((row, how), (2, 'row 2 shared, moved'))
        self.assertEqual(F.check(out, model, self.nb), [])
        u, v = cells[0]
        self.assertEqual(F.parse_tim(out)[3][v * 256 + u], 15)     # the icon's corner texel: row 2's transparent entry

    def test_full_page_moves_islands(self):
        """6x6 islands every 8 texels over the whole page but a 10-texel strip: no 15x15 cell anywhere, but islands fit
        the strip; the frames get their four cells and every face reads what it read."""
        faces = []
        for y in range(0, 118, 8):
            for x in range(0, 250, 8):
                faces.append(([(x, y), (x + 6, y), (x, y + 6)], 0))
                faces.append(([(x + 6, y), (x + 6, y + 6), (x, y + 6)], 0))
        model = self.with_faces(faces, keep=False)
        tex = self.without_frames()
        with self.assertRaises(F.NoRoom):
            F.place(F.model_use(model, self.nb)[0])
        out, moved, cells, row, how = F.stamp(tex, model, self.nb, F.mono(icon()))
        self.assertIn('UV islands moved', how)
        self.assertNotEqual(moved, model)
        self.assertEqual(len(moved), len(model))
        self.assertEqual(F.check(out, moved, self.nb), [])
        self.same_texels(model, tex, moved, out)
        self.assertEqual(self.mmd.MMD.parse(moved, self.nb).build(), moved)

    def test_small_texture_completed(self):
        import species
        tex = self.mmd.alltim_entry(Path(species.ALLTIM).read_bytes(), 121)     # Cherrymon: 2 CLUT rows, 96 rows
        model = Path(species.originals().model_path(121)).read_bytes()
        nb = len(species.originals().rec[121]['bones'])
        self.assertTrue(F.check(tex))
        out, _, cells, row, how = F.stamp(tex, model, nb, F.mono(icon()))
        rows = F.parse_tim(out)[0]
        self.assertEqual(struct.unpack_from('<HH', out, 16), (16, 16))
        self.assertEqual(F.check(out, model, nb), [])
        self.assertEqual(rows[:2], F.parse_tim(tex)[0][:2])


@unittest.skipUnless(EXTRACTED, 'needs extracted/')
class Originals(unittest.TestCase):
    def test_only_npc_originals_lack_frames(self):
        """The disc's own species all have their four frames but the NPC-only ones (Analogman .. DemiMeramon, 116-127:
        species.build_alltim and the record originals give them theirs), and no disc texture has a trailer."""
        import mmd
        import species
        data = Path(species.ALLTIM).read_bytes()
        lack = [t for t in range(1, 180) if F.check(mmd.alltim_entry(data, t))]
        self.assertTrue(lack and set(lack) <= {62} | set(range(116, 128)), lack)     # 62: an empty entry
        self.assertTrue(all(F.trailer(mmd.alltim_entry(data, t)) is None for t in range(180)))


if __name__ == '__main__':
    unittest.main()
