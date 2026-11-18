"""DW2 effect decoding and the effect-script disassembler, on synthetic bytes (no disc needed)."""
import struct
import unittest

from tools import dw2effect as fx
from tools import efescript as efe


def _model(tex_move=None):
    """One bone with four vertices and one additive quad, then a 4bpp 4x2 texture."""
    count = 1
    head = 12 + 16 * count + 10 * 3                    # tables, then two blink slots and one more entry
    verts = head
    vlist = struct.pack('<h4x', 4) + struct.pack('<12h', 0, 0, 0, 100, 0, 0, 0, 100, 0, 100, 100, 0)
    norms = verts + len(vlist)
    nlist = struct.pack('<h4x', 0)
    polys = norms + len(nlist)
    quad = bytes([0, 1, 2, 3]) + b'\0' * 4 + bytes([0, 0, 3, 0, 0, 1, 3, 1]) + struct.pack('<2H', 1 << 6, 1 << 5)
    plist = struct.pack('<i', 1) + quad + struct.pack('<3i', 0, 0, 0)
    tim_off = polys + len(plist)
    tim = struct.pack('<2I', 0x10, 2) + struct.pack('<I4H', 12 + 8, 0, 0, 1, 2) + struct.pack('<2H', 0x4321, 0x8001)
    tables = struct.pack('<4i', verts, norms, polys, 0)
    slots = b'\0' * 20 + (tex_move or b'\xff' + b'\0' * 9)
    return struct.pack('<3I', tim_off, 0, count) + tables + slots + vlist + nlist + plist + tim


def _anim():
    """Keys: 0 identity, 1 scaled by (2, 1, 0) and moved; frames 0, 1, 1."""
    keys = struct.pack('<9h3h', 4096, 0, 0, 0, 4096, 0, 0, 0, 4096, 0, 0, 0)
    keys += struct.pack('<9h3h', 8192, 0, 0, 0, 4096, 0, 0, 0, 0, 10, 20, -30)
    table = 4 + 4 + 4
    first = table + len(keys)
    return struct.pack('<I', 1) + struct.pack('<I', table) + struct.pack('<I', first) + keys + bytes([0, 1, 1, 0xFF, 0])


class EffectObject(unittest.TestCase):
    def test_parse(self):
        e = fx.parse_effect(_model(), _anim())
        self.assertEqual(len(e.bones), 1)
        self.assertEqual(e.bones[0].vertices[1], (100, 0, 0))
        p = e.bones[0].prims[0]
        self.assertEqual((p.verts, p.uvs[2], p.clut, p.blend), ((0, 1, 2, 3), (0, 1), 64, 1))
        self.assertEqual(e.frames, [[0], [1], [1]])
        self.assertEqual(sorted(e.keys[0]), [0, 1])
        self.assertEqual(e.tex_moves, [])

    def test_world_and_scale(self):
        e = fx.parse_effect(_model(), _anim())
        r, t = fx.world(e, 1)[0]
        self.assertEqual((r[0][0], r[2][2], t), (2.0, 0.0, [10, 20, -30]))
        self.assertEqual(fx.scale_of(r), 2.0)
        self.assertEqual(fx.shear(r), 0.0)
        self.assertGreater(fx.shear([[1, 1, 0], [0, 1, 0], [0, 0, 1]]), 0.5)
        self.assertFalse(fx.mirrored(r))                                # flattened, completed by the cross product
        self.assertTrue(fx.mirrored([[-1, 0, 0], [0, 1, 0], [0, 0, 1]]))

    def test_texture_blocks(self):
        e = fx.parse_effect(_model(bytes([4, 5, 2, 3, 0, 0, 2, 0, 4, 0])), _anim())
        # the quad's box overlaps the first flipbook frame (8 x 3 at 0, 0); the other frames stay apart
        self.assertEqual(fx.uv_blocks(e), [(0, 0, 7, 2), (8, 0, 15, 2), (16, 0, 23, 2)])
        self.assertEqual(fx.shelf_pack([(200, 32), (56, 16), (56, 16)]), [(0, 0), (200, 0), (200, 16)])
        self.assertIsNone(fx.shelf_pack([(40, 40)]))
        self.assertIsNone(fx.shelf_pack([(200, 32), (100, 10)]))

    def test_cycle_tex_move(self):
        e = fx.parse_effect(_model(bytes([4, 5, 2, 3, 0, 0, 2, 0, 4, 0])), _anim())
        self.assertEqual(len(e.tex_moves), 1)
        m = e.tex_moves[0]
        self.assertEqual((m.dst, m.size, m.frames, m.ticks), ((4, 5), (2, 3), [(0, 0), (2, 0), (4, 0)], 8))

    def test_texture_and_blend(self):
        e = fx.parse_effect(_model(), _anim())
        image = fx.tim_halfwords(e.tim)
        self.assertEqual(image, [[0x4321], [0x8001]])
        self.assertEqual(fx.texel(image, 1 << 6, 0, 0), 0x8001)       # index 1 on palette row 1
        self.assertEqual(fx._blend((200, 10, 0), (100, 10, 0), 1), (255, 20, 0))
        self.assertEqual(fx._blend((200, 10, 0), (100, 20, 0), 2), (100, 0, 0))

    def test_budget(self):
        b = fx.efe_budget([fx.parse_effect(_model(), _anim())])
        self.assertEqual((b['objects'], b['poses'], b['palettes'], b['texels'], b['mirrored_poses']), (1, 2, 1, 8, 0))
        self.assertTrue(all(b['fits'].values()))


class Tables(unittest.TestCase):
    def test_skill_record(self):
        rec = bytearray(0x44)
        struct.pack_into('<I', rec, 0, 22 | 1 << 16 | 6 << 20)
        struct.pack_into('<BBhh', rec, 4, 32, 1, 3237, 50)
        struct.pack_into('<I', rec, 0x24, 4 + 0x44 * 2)
        struct.pack_into('<12h', rec, 0x2C, 0, 966, 0, 0, 928, 0, 0, 969, 0, 0, 931, 0)
        data = struct.pack('<I', 4) + bytes(rec) + bytes(0x44) + bytes([0x16, 0x24, 0xFD, 0x0B, 0x49, 2, 0xFF])
        s = fx.parse_skills(data)[22]
        self.assertEqual((s.name, s.mp, s.power, s.cast, s.target, s.xa), ('Ma B-2', 32, 50, 1, 6, (3237, 1)))
        self.assertEqual((s.cast_fx[1], s.hit_fx[1]), ((966, 928), (969, 931)))

    def test_digimon_record(self):
        rec = bytearray(0x28)
        struct.pack_into('<Ii', rec, 0, 8 + 0x28 * 2, 189 << 1)
        struct.pack_into('<h', rec, 6, 77)
        struct.pack_into('<5h', rec, 0x1E, 2137, 1408, 0, 1, 1)
        rows = 8 + 0x28 * 2 + 2
        data = struct.pack('<2I', 8, rows) + bytes(rec) + bytes(0x28) + bytes([0x0A, 0xFF])
        data += struct.pack('<6h', 0, 1024, 1024, 0, 1664, 384)
        d = fx.parse_digimon(data)[189]
        self.assertEqual((d.name, d.model, d.head, d.hit_y), ('A', 77, 2137, 1408))
        self.assertEqual(d.cast_rows, [(0, 1024, 1024), (0, 1664, 384), (0, 1664, 384)])


class EffectScript(unittest.TestCase):
    def test_round_trip(self):
        a = efe.Asm(0x100)
        a.label('top')
        a.ld(20)
        a.br('<', 0, 0, 'done')
        a.ldx(0x14, 0, 0)
        a.op('add', 4, 0)
        a.pusha(4, 0)
        a.push(0)
        a.sub('drawTMD')
        a.jmp('top')
        a.label('done')
        a.ret()
        code = a.bytes()
        base = bytes(0x100) + code
        listing, pc = [], 0x100
        while pc < len(base):
            text, size, _ends, _t = efe.decode(base, pc)
            listing.append(text)
            pc += size
        self.assertEqual(listing, ['ld 20', 'if inst+0x0.i32 < R goto 0x132', 'ldx.i16 base+0x14[i32 inst+0x0]',
                                   'add.i32 inst+0x4, R', 'pusha inst+0x4', 'push 0', 'sub drawTMD', 'jmp 0x100', 'ret'])

    def test_chunk_listing(self):
        a = efe.Asm(0)
        a.sub('faceTargetEntity')
        a.ret()
        script = a.bytes()
        body = script + bytes(0x20)
        chunk = struct.pack('<13i', 0, 0, len(script), len(script), len(script), len(body), len(body), len(body),
                            len(body), len(body), 3, 0, 0x13F) + body
        self.assertEqual(efe.header(chunk)['effectId'], 0x13F)
        self.assertIn('sub faceTargetEntity', efe.listing(chunk))


if __name__ == '__main__':
    unittest.main()
