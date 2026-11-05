#!/usr/bin/env python3
"""tools/flatsprite.py gives every texture the frames a flattened Digimon is drawn with, where the model leaves room.

  tools/test_flatsprite.py

Asset-free: the span rasteriser against tools/models/audit_textures.py's, the silhouette conversion, the placement
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
    def test_native_field_texture_policy(self):
        import species
        for t in (66, 67, 88, 102, 111):
            self.assertTrue(species.needs_authored_flat({'id': t}))
            self.assertTrue(species.needs_authored_flat({'id': 200, 'texture': {'from': t}}))
        for t in (3, 51, 65, 103, 112):
            self.assertFalse(species.needs_authored_flat({'id': t}))
        self.assertFalse(species.needs_authored_flat({'id': 471, 'texture': {'file': 'owned.TIM'}}))

    def test_spans_match_the_audit(self):
        rnd = random.Random(7)
        for _ in range(3000):
            n = rnd.choice((3, 4))
            k = rnd.choice((6, 40, 200))
            uv = [(rnd.randint(0, k), rnd.randint(0, min(k, 127))) for _ in range(n)]
            self.assertEqual(F.texels(uv), A.texels(uv, 256, 256), uv)

    def test_mono_silhouette_ignores_body_shading(self):
        # All-dark and all-light bodies have the same white interior and outline.
        dark = F.mono(icon((0x0421, 0x2108, 0x2108)))
        light = F.mono(icon((0x0421, 0x7FFF, 0x7FFF)))
        self.assertEqual(dark, light)
        self.assertEqual(struct.unpack_from('<16H', dark), (0, F.OUTLINE, F.FILL) + (0,) * 13)
        frames = self.unpack_icon(dark)
        self.assertEqual(frames[0][1][1], 1)
        self.assertEqual(frames[0][7][7], 2)
        self.assertEqual(frames[0][0][0], 0)

    @staticmethod
    def unpack_icon(blob):
        return [[[(blob[32 + ((f >> 1) * 16 + y) * 16 + ((f & 1) * 16 + x) // 2] >> (4 * (x & 1))) & 15
                   for x in range(16)] for y in range(16)] for f in range(4)]

    def test_mono_fits_visible_area_and_animates_static_art(self):
        import portraits
        still = [[2] * 16 for _ in range(16)]
        blob = portraits._pack([0, F.OUTLINE, F.FILL] + [0] * 13, [still] * 4)
        frames = self.unpack_icon(F.mono(blob))
        self.assertEqual(len({tuple(map(tuple, fr)) for fr in frames}), 4)
        for fr in frames:
            self.assertFalse(any(fr[15]))
            self.assertFalse(any(row[15] for row in fr))
            for y in range(15):
                for x in range(15):
                    if fr[y][x] and any(not (0 <= x + dx < 15 and 0 <= y + dy < 15) or not fr[y + dy][x + dx]
                                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                        self.assertEqual(fr[y][x], 1)

    def test_mono_retains_a_strong_eye_without_shading(self):
        import portraits
        fr = [[0] * 16 for _ in range(16)]
        for y in range(2, 14):
            for x in range(2, 14):
                fr[y][x] = 2
        fr[5][6] = 1
        blob = portraits._pack([0, F.OUTLINE, F.FILL] + [0] * 13, [fr] * 4)
        out = self.unpack_icon(F.mono(blob))[0]
        self.assertEqual(out[6][5], 1)  # common bounds centred and bottom-aligned
        self.assertEqual(out[7][5], 2)

    def test_colour_frames_are_not_preserved_as_native(self):
        rows = [[0] * 16 for _ in range(16)]
        rows[F.ROW][:3] = [0, F.OUTLINE, 0x03E0]
        idx = bytearray(F.W * F.H)
        for u, v in F.NATIVE:
            idx[(v + 1) * F.W + u + 1] = 2
        idx[(F.NATIVE[0][1] + 2) * F.W + F.NATIVE[0][0] + 2] = 1
        rows[F.ROW][3] = 0x001F
        idx[(F.NATIVE[0][1] + 3) * F.W + F.NATIVE[0][0] + 3] = 3
        tex = F.build_tim(rows, 0, 0, idx, 0, 0)
        self.assertTrue(any('3 opaque colours' in p for p in F.check(tex)))
        idx[(F.NATIVE[0][1] + 3) * F.W + F.NATIVE[0][0] + 3] = 0
        use = F.Use([])
        self.assertFalse(F.native_sprite_ok(rows, idx, (use, use), set()))
        rows[F.ROW][2] = F.FILL
        self.assertTrue(F.native_sprite_ok(rows, idx, (use, use), set()))
        rows[F.ROW][1:3] = [0x8000, 0xFFFF]
        self.assertTrue(F.native_sprite_ok(rows, idx, (use, use), set()))

    def test_drawn_animations_have_four_visible_two_colour_poses(self):
        import portraits
        for path in sorted((ROOT / 'content/icons').glob('*.txt')):
            with self.subTest(icon=path.stem):
                blob = F.mono(portraits.drawn_icon(path.read_text()))
                frames = self.unpack_icon(blob)
                self.assertEqual(len({tuple(map(tuple, fr)) for fr in frames}), 4)
                for fr in frames:
                    self.assertTrue(any(c for row in fr for c in row))
                    self.assertFalse(any(fr[15]))
                    self.assertFalse(any(row[15] for row in fr))
                    self.assertLessEqual({c for row in fr for c in row}, {0, 1, 2})

    def test_shared_cells_decode_every_pose_without_extra_texels(self):
        for cells in (((10, 10), (40, 10), (10, 10), (40, 10)), ((10, 10),) * 4):
            with self.subTest(cells=cells):
                blob = F.mono(icon())
                rows = [[0] * 16 for _ in range(16)]
                idx = bytearray(F.W * F.H)
                pose_rows = F.palette_frames(blob, cells, rows, idx, {0, 1})
                tex = F.build_tim(rows, 0, 0, idx, 0, 0) + F.MAGIC + bytes(c for uv in cells for c in uv) + bytes(pose_rows)
                frames = F.frames_of(tex)
                self.assertEqual(len({tuple(tuple(r[:15]) for r in fr[:15]) for fr in frames}), 4)
                self.assertEqual(F.check(tex), [])
                self.assertFalse(set(pose_rows) & {0, 1})
                if len(set(cells)) == 2:
                    source = self.unpack_icon(blob)
                    self.assertEqual([[[0 if c == 0 else F.OUTLINE if c == 1 else F.FILL for c in r[:15]]
                                       for r in fr[:15]] for fr in source],
                                     [[r[:15] for r in fr[:15]] for fr in frames])

    def test_place_prefers_the_originals_corner(self):
        free = F.Use([])
        self.assertEqual(F.place((free, free)), F.NATIVE)

    def test_place_moves_to_a_free_block(self):
        marks = [(x, y) for x in range(256) for y in range(128) if not (10 <= x < 50 and 20 <= y < 60)]
        cells = F.place((F.Use(marks), F.Use(marks, 0)))
        self.assertEqual(len(set(cells)), 4)
        for u, v in cells:
            self.assertTrue(11 <= u and u + F.CELL <= 49 and 21 <= v and v + F.CELL <= 59, cells)

    def test_placement_does_not_wrap_the_gpu_uv_endpoint(self):
        for x0, y0, fits in ((240, 112, True), (241, 113, False)):
            marks = [(x, y) for y in range(F.H) for x in range(F.W)
                     if not (x0 <= x < x0 + F.CELL and y0 <= y < y0 + F.CELL)]
            use = F.Use(marks, 0)
            if fits:
                for u, v in F.place((use, use)):
                    self.assertLess(u + F.CELL, F.W)
                    self.assertLess(v + F.CELL, F.H)
            else:
                with self.assertRaises(F.NoRoom):
                    F.place((use, use))

    def test_place_shares_cells_when_short(self):
        holes = [(5, 5), (100, 70)]       # two 17x17 holes only: a 15x15 cell and its margin each
        marks = [(x, y) for x in range(256) for y in range(128)
                 if not any(hx <= x < hx + 17 and hy <= y < hy + 17 for hx, hy in holes)]
        cells = F.place((F.Use(marks), F.Use(marks, 0)))
        self.assertEqual(sorted(set(cells)), sorted((x + 1, y + 1) for x, y in holes))
        reserved = F.place((F.Use(marks), F.Use(marks, 0)), keep=((101, 71),))
        self.assertEqual(reserved[0], (101, 71))
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
            r, r2 = A.row_of(d1['cba']), A.row_of(d2['cba'])
            for x, y in F.texels(d1['uv']):
                for X, Y in ((x + ex, y + ey) for ex in (-1, 0, 1) for ey in (-1, 0, 1)):
                    if 0 <= X < 256 and 0 <= Y < 128 and 0 <= X + dx < 256 and 0 <= Y + dy < 128:
                        self.assertEqual(ro[r][io[Y * 256 + X]], rn[r2][inn[(Y + dy) * 256 + X + dx]])

    def test_own_frames_kept(self):
        out, model, cells, row, how = F.stamp(self.tex, self.model, self.nb, F.mono(icon()))
        self.assertEqual((cells, row, how, model), (F.NATIVE, F.ROW, 'its own', self.model))
        self.assertEqual(F.frames_of(out), F.frames_of(self.tex))
        self.assertEqual(F.trailer(out), (F.NATIVE, F.ROW))
        self.assertEqual(F.check(out, self.model, self.nb), [])
        self.assertEqual(len(out), F.TEX_SIZE)

    def test_monochrome_frames_are_replaced_when_source_is_not_trusted(self):
        drawn = F.mono(icon())
        self.assertFalse(F.matches_art(self.tex, drawn))
        out, model, cells, row, how = F.stamp(self.tex, self.model, self.nb, drawn, keep_native=False)
        self.assertNotEqual(how, 'its own')
        self.assertEqual(model, self.model)
        self.assertTrue(F.matches_art(out, drawn))
        self.same_texels(self.model, self.tex, model, out)

    def test_native_yanmamon_noise_is_not_accepted_as_art(self):
        import species
        data = (ROOT/'extracted/CHDAT/ALLTIM.TIM').read_bytes()
        content = species.load_content()
        for t in (67, 102):
            with self.subTest(species=t):
                record = species.originals().rec[t]
                model = (ROOT/f'extracted/CHDAT/MMD{t//30}'/(record['modelName']+'.MMD')).read_bytes()
                tex = data[t*F.TEX_SIZE:(t+1)*F.TEX_SIZE]
                drawn = F.mono(F.art(content[t])[0])
                # The old palette-only audit passes this scrambled square.
                self.assertEqual(F.check(tex), [])
                self.assertFalse(F.matches_art(tex, drawn))
                out, moved, _, _, _ = F.stamp(tex, model, record['para']['boneCount'], drawn, keep_native=False)
                self.assertEqual(moved, model)
                self.assertTrue(F.matches_art(out, drawn))
                self.same_texels(model, tex, moved, out)

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
        # Reserve every existing frame while making another window. Relocation
        # must not trade one free frame for another, including overlapping sources.
        kept_model, kept_idx = F.make_room(moved, self.nb, F.parse_tim(out)[3], keep=cells)
        uses = F.model_use(kept_model, self.nb)[0]
        for u, v in cells:
            self.assertTrue(uses[0].free(u, v, F.CELL, F.CELL))
        rows, cx, cy, _, px, py, _ = F.parse_tim(out)
        kept_tex = F.build_tim(rows, cx, cy, kept_idx, px, py)
        self.same_texels(moved, out, kept_model, kept_tex)

    def test_palette_compaction_preserves_every_sampled_colour(self):
        model = self.with_faces([([(2, 2), (8, 2), (2, 8)], 0),
                                 ([(22, 2), (28, 2), (22, 8)], 1)], keep=False)
        parsed = self.mmd.MMD.parse(model, self.nb)
        for animation in parsed.anims.anims:
            if animation:
                animation.instrs = [ins for ins in animation.instrs if ins['op'] != 'tex']
        model = parsed.build()
        rows, cx, cy, idx, px, py, _ = F.parse_tim(self.tex)
        rows[0] = [F.OUTLINE, F.FILL] + [0] * 14
        rows[1] = [F.FILL, F.OUTLINE] + [0] * 14
        for y in range(10):
            for x in range(30):
                idx[y * F.W + x] = x & 1
        tex = F.build_tim(rows, cx, cy, idx, px, py)
        merged, pixels = F.merge_palette(model, self.nb, rows, idx)
        self.assertEqual(len(F.model_use(merged, self.nb)[1]), 1)
        self.same_texels(model, tex, merged, F.build_tim(rows, cx, cy, pixels, px, py))
        self.assertEqual(len(model), len(merged))

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
