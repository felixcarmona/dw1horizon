#!/usr/bin/env python3
"""Tests of tools/dw3effect.py, tools/dw3sprite.py and tools/dw3efe.py: synthetic scripts and tables, then
(with DW3_IMAGE and DW3_ROOT set) the real disc's tables, a conversion and its fidelity check."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools import dw3effect as X            # noqa: E402
from tools import dw2effect as D            # noqa: E402


def words(*ops):
    return tuple(w for op in ops for w in op)


class Script(unittest.TestCase):
    def test_lengths(self):
        self.assertEqual(X.op_len((3, 1, 25), 0), 3)               # preload a sprite
        self.assertEqual(X.op_len((3, 0, 2, 0, 0, 32767), 0), 6)
        self.assertEqual(X.op_len((6, 0, 85, 0, 0, 0, 0, 0, 0), 0), 9)
        self.assertEqual(X.op_len((5, 0, 0, 5), 0), 4)             # camera preset
        self.assertEqual(X.op_len((5, 0, 1) + (0,) * 14, 0), 17)   # camera keyframe
        self.assertEqual(X.op_len((2, 0, 0, 50), 0), 4)
        self.assertIsNone(X.op_len((42,), 0))

    def test_timeline(self):
        w = words((2, 0, 0, 50), (11, 10), (6, 0, 85, 448, 4416, 4736, 0, 2048, 0), (11, 30), (10, 99, 0),
                  (11, 5), (0xFF,))
        t = X.technique('M372SGRG', 11, w)
        self.assertEqual(t.length, 45)
        self.assertEqual(t.hits, [40])
        self.assertEqual(t.clips, [50])
        s, = t.spawns
        self.assertEqual((s.tick, s.kind, s.id), (10, 'meft', 85))
        self.assertEqual(s.pos, (448, -4416, -4736))
        self.assertEqual(s.rot, (0, -2048, 0))

    def test_strict_end(self):
        with self.assertRaises(ValueError):
            X.disassemble((11, 1, 0xFF, 3))
        with self.assertRaises(ValueError):
            X.disassemble((11, 1))

    def test_script_section(self):
        body = struct.pack('<2h', 11, 0xFF)
        table = struct.pack('<4I', 16, 20, 0, 0)
        sec = table + body + struct.pack('<h', 0xFF) + b'\0\0'
        si, scripts = X.script_section([b'junk', sec])
        self.assertEqual(si, 1)
        self.assertEqual(sorted(scripts), [0, 1])


class Names(unittest.TestCase):
    def test_decode(self):
        raw = bytes([0x15, 0x28 + 14, 0x28 + 19, 1, 1, 0x15, 0x28 + 4, 0x28 + 0, 0x28 + 3])
        self.assertEqual(X.decode_name(raw), 'Hot Head')
        self.assertEqual(X.decode_name(bytes([0x21, 1, 0x1A, 0x20])), 'T-S')

    def test_lang(self):
        data = struct.pack('<3I', 2, 12, 14) + b'\x0e\0\x0f\0'
        self.assertEqual(X.lang_strings(data), ['A', 'B'])


class Tables(unittest.TestCase):
    def test_partners(self):
        exe = bytearray(64)
        for k in range(52):
            rec = bytearray(X.PARTNER_SIZE)
            struct.pack_into('<H', rec, 0, 300 + k)
            struct.pack_into('<H', rec, 40, 53 + k)
            exe += rec
        off, sig = X.locate_partners(bytes(exe), set(range(300, 360)), 200)
        self.assertEqual(off, 64)
        self.assertEqual(sig[300], 53)
        self.assertEqual(sig[351], 104)

    def test_meft_table(self):
        rows = [(39, 4, 2000, 0, 2000), (65, 6, 2001, 0, 2001), (65, 6, 2001, 0, 2001), (66, 0, 2002, 8, 2002)]
        rows += [(100 + k, 4, 2003 + k, 0, 2003 + k) for k in range(60)]
        data = b'\xff' * 8 + b''.join(struct.pack('<IHHHH', *r) for r in rows) + bytes(24)
        t = X.locate_meft_table(data)
        self.assertEqual(t[65], (6, 2001))
        self.assertEqual(t[66], (0, 2002))
        self.assertEqual(len(t), 63)


class Placement(unittest.TestCase):
    def effect(self):
        bone = D.Bone(-1, [(0, 0, 0), (100, 0, 0), (0, 0, -100)], [])
        keys = [{0: ((4096, 0, 0, 0, 4096, 0, 0, 0, 4096), (0, 0, -1000))}]
        tim = struct.pack('<II', 0x10, 0) + struct.pack('<I4H', 14, 0, 0, 1, 1) + bytes(2)
        return D.Effect([bone], tim, keys, [[0], [0]])

    def test_partner_faces_target(self):
        # a partner stands at -FIELD_HALF facing +z; its spawn turned half a turn flies toward the target
        s = X.Spawn(0, 'meft', 1, (0, -500, -X.FIELD_HALF + 300), (0, -2048, 0))
        e = X.baked(self.effect(), s, -1)
        m, t = e.keys[0][0]
        self.assertEqual(t, (0, -500, -1300))          # 300 ahead, then the effect's own 1000 forward
        self.assertEqual(m[8], 4096)                   # no turn left in the caster's frame

    def test_enemy_faces_target(self):
        s = X.Spawn(0, 'meft', 1, (0, -500, X.FIELD_HALF - 300), (0, 0, 0))
        m, t = X.baked(self.effect(), s, 1).keys[0][0]
        self.assertEqual(t, (0, -500, -1300))
        self.assertEqual(m[0], 4096)

    def test_delay(self):
        s = X.Spawn(0, 'meft', 1, (0, 0, -X.FIELD_HALF), (0, -2048, 0))
        e = X.baked(self.effect(), s, -1, delay=3)
        self.assertEqual(len(e.frames), 5)
        hidden = e.keys[0][e.frames[0][0]]
        self.assertEqual(D.scale_of([[hidden[0][3 * r + k] / 4096 for k in range(3)] for r in range(3)]), 0)


class Fidelity(unittest.TestCase):
    def frames(self, boxes):
        from tools import image as img
        out = []
        for b in boxes:
            f = img.new('RGB', (64, 36), (28, 30, 40))
            if b:
                img.ImageDraw.Draw(f).rectangle(b, fill=(250, 220, 255))
            out.append(f)
        return out

    def test_faithful(self):
        from tools import dw3efe as E
        src = self.frames([None, (10, 10, 30, 20), (12, 8, 40, 30), (20, 10, 50, 30), None])
        dst = self.frames([None, (11, 10, 29, 21), (12, 9, 38, 30), (22, 10, 50, 28), None])
        ok, why = E.passes(E.fidelity(src, dst))
        self.assertTrue(ok, why)

    def test_one_frame_late_follows(self):
        from tools import dw3efe as E
        src = [0, 5, 0, 9, 0, 3, 0, 7, 0]
        self.assertLess(E._corr(src[:-1], src[1:]), 0)
        self.assertAlmostEqual(E._corr_near(src[:-1], src[1:]), 1.0)

    def test_mostly_empty_fails(self):
        from tools import dw3efe as E
        src = self.frames([None, (10, 10, 30, 20), (12, 8, 40, 30), (20, 10, 50, 30), (0, 0, 63, 35)])
        dst = self.frames([None, (11, 10, 14, 13), None, None, None])
        f = E.fidelity(src, dst)
        ok, why = E.passes(f)
        self.assertFalse(ok)
        self.assertGreater(f['empty'], 0.5)
        self.assertLess(f['area'], 0.1)

    def test_elsewhere_fails(self):
        from tools import dw3efe as E
        src = self.frames([(0, 0, 15, 15), (0, 0, 20, 20), (0, 0, 15, 15)])
        dst = self.frames([(45, 18, 60, 33), (40, 14, 60, 34), (45, 18, 60, 33)])
        ok, why = E.passes(E.fidelity(src, dst))
        self.assertFalse(ok)
        self.assertTrue(any('overlap' in w for w in why))


DISC = os.environ.get('DW3_IMAGE')


@unittest.skipUnless(DISC and os.path.isfile(DISC) and os.environ.get('DW3_ROOT'), 'needs DW3_IMAGE and DW3_ROOT')
class Disc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.disc = X.Disc(DISC)
        cls.tables = X.Tables(cls.disc)

    def test_tables(self):
        t = self.tables
        self.assertEqual(len(t.names), 444)
        self.assertEqual(len(t.moves), 443)
        self.assertEqual(t.move('Giant Missile').power, 400)
        self.assertEqual(t.moves[t.partners[372]].name, 'Giant Missile')
        self.assertEqual(t.moves[t.partners[394]].name, 'Mugenhadou')
        self.assertIn(364, t.meft)
        self.assertEqual(t.sprite_files[t.sprites[2041][0]], 'E373RENA.BIN')

    def test_every_script(self):
        for name in sorted(self.disc.base):
            if name.startswith('M') and name.endswith('.BIN') and name[1:4].isdigit():
                X.model_scripts(self.disc, name)          # strict: every script ends cleanly

    def test_sprite(self):
        from tools import dw3sprite
        frames = dw3sprite.render(self.disc, self.tables, 2003)
        pack, blocks = dw3sprite.sprite_blocks(self.disc, self.tables, 2003)
        n = max(b.count for b in blocks)                            # 60 Hz ticks, drawn at 30 frames a second
        self.assertEqual(len(frames), -(-n // 2))
        self.assertGreater(len(frames), 5)
        self.assertTrue(any(f.getbbox() for f in frames))

    def test_convert(self):
        from tools import dw3efe as E
        tech = X.model_scripts(self.disc, 'M366GIRU')[11]
        table = struct.pack('<5h', 5, 5, 40, -30, 0) + struct.pack('<5h', -1, 0, 0, 0, 0)
        chunk, info = E.convert(self.disc, self.tables, tech, 0.2, table, 0x17A)
        self.assertEqual(len(chunk), E.CHUNK_SIZE)
        self.assertEqual(info['objects'], ['MEFT0102'])
        self.assertEqual(info['kept'], info['frames'])           # the whole effect, not DW2's two seconds
        self.assertNotIn('left_out', info)
        _s, e = X.staged_effects(self.disc, self.tables, tech)[0]
        b = next(b for b, bone in enumerate(e.bones) if bone.prims)
        _chunk, info = E.convert(self.disc, self.tables, tech, 0.2, table, 0x17A, leave_out=[(0, b)])
        self.assertEqual(info['left_out'], [f'MEFT0102 part {b} ({len(e.bones[b].prims)} faces)'])

    def test_converted_looks_like_the_original(self):
        from tools import dw3efe as E
        efe_path = os.path.join(E.ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')
        if not os.path.isfile(efe_path):
            self.skipTest('needs extracted/ETCHI/EFEDAT.EFE')
        efe = open(efe_path, 'rb').read()
        tech = X.model_scripts(self.disc, 'M366GIRU')[11]
        chunk, _info = E.convert(self.disc, self.tables, tech, E.FIELD_SCALE,
                                 E.launch_table(E.native_chunk(efe, 59)), 0x17A)
        _frames, fid = E.compare(self.disc, self.tables, tech, chunk, 'Guilmon', 320, 180)
        ok, why = E.passes(fid)
        self.assertTrue(ok, why)

    def test_sprite_effect(self):
        from tools import dw3sprite as P
        e = P.effect(self.disc, self.tables, 2)                     # the shared hit spark
        pack, blocks = P.sprite_blocks(self.disc, self.tables, 2)
        self.assertEqual(len(e.frames), -(-max(b.count for b in blocks) // 2))   # 60 Hz ticks, posed at 30 fps
        self.assertTrue(all(v[0] == 0 for bone in e.bones for v in bone.vertices))   # flat, facing the side
        image = D.tim_halfwords(e.tim)
        self.assertEqual(len(image[0]), P.TIM_W)
        self.assertLessEqual(len(image), 256)
        self.assertTrue(any(k for row in e.frames for k in row))        # some bone shows

    def test_sprite_conversion_looks_like_the_original(self):
        from tools import dw3efe as E
        efe_path = os.path.join(E.ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')
        if not os.path.isfile(efe_path):
            self.skipTest('needs extracted/ETCHI/EFEDAT.EFE')
        efe = open(efe_path, 'rb').read()
        tech = X.model_scripts(self.disc, 'M241HNGY')[5]               # Divermon: one hit spark
        chunk, info = E.convert(self.disc, self.tables, tech, E.FIELD_SCALE,
                                E.launch_table(E.native_chunk(efe, 85)), 0x100 + E.EFFECT_IDS[304])
        self.assertEqual(info['objects'], ['sprite 2'])
        _frames, fid = E.compare(self.disc, self.tables, tech, chunk, 'Divermon', 320, 180)
        ok, why = E.passes(fid)
        self.assertTrue(ok, why)

    def test_effect_ids(self):
        from tools import dw3efe as E
        self.assertEqual(len(set(E.EFFECT_IDS.values())), len(E.EFFECT_IDS))
        self.assertTrue(all(196 <= i <= 222 for k, i in E.EFFECT_IDS.items() if k in E.MEFT_KEYS))
        self.assertTrue(all(223 <= i <= 250 for k, i in E.EFFECT_IDS.items() if k in E.SPRITE_KEYS))

if __name__ == '__main__':
    unittest.main()
