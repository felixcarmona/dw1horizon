"""Tests for tools/dcbeffect.py and tools/dcbefe.py on synthetic scripts, sheets and sprites (no disc data)."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import dcbeffect as C, dcbefe, dw2efe    # noqa: E402


class Script:
    """A tiny MSCD assembler."""

    def __init__(self):
        self.code = b''

    def _put(self, b):
        b += b'\0' * (-len(b) % 4)
        self.code += b
        return self

    def set(self, var, value, sub=0):
        return self._put(struct.pack('<HHHHi', 7, var, sub, 0, value))

    def skip(self, var, value, sub=0):
        return self._put(struct.pack('<HHHHi', 9, var, sub, 0, value))

    def jmp(self, target):
        return self._put(struct.pack('<HHI', 5, 0, target))

    def cmd(self, group, n, *args):
        k = 'ABCDE'.index(group)
        assert len(args) == k
        return self._put(struct.pack('<HH', 0xa + k, n) + b''.join(struct.pack('<Hh', 0, a) for a in args))

    def bytes(self):
        return b'MSCD' + struct.pack('<III', 3, 16 + len(self.code), C.NVARS) + self.code


def straight(slot=1, kind=15, model=7, start=(0, 0, 0), end=(0, 0, -1000), speed=50, wait=20):
    s = Script()
    for i, x in enumerate(start):
        s.set(C.V_START + i, x)
    for i, x in enumerate(end):
        s.set(C.V_END + i, x)
    s.set(C.V_SPEED, speed).set(C.V_MOTION, 11).set(C.V_MODEL, model)
    for i in range(3):
        s.set(C.V_SCALE + i, 4096).set(C.V_SCALE_END + i, 4096)
    s.cmd('C', 0, slot, kind).cmd('B', 8, slot).set(0, -1).cmd('B', 10, wait).cmd('B', 9, slot)
    return s


class Decode(unittest.TestCase):
    def test_instructions(self):
        s = Script().set(5, 3).skip(5, 3).jmp(0).cmd('B', 10, 4).cmd('C', 0, 1, 15)
        ops = [(i.op, i.a) for i in C.decode(s.bytes())]
        self.assertEqual(ops, [('set', 5), ('skip', 5), ('jmp', 0), ('cmdB', 10), ('cmdC', 0)])

    def test_unknown_op(self):
        with self.assertRaises(ValueError):
            C.decode(b'MSCD' + struct.pack('<III', 3, 20, 4) + struct.pack('<HH', 1, 0))


class Trace(unittest.TestCase):
    def test_object_lifetime(self):
        tr = C.trace(straight(wait=20).bytes())
        (inst,) = tr.instances
        self.assertEqual((inst.slot, inst.kind, inst.start, inst.end), (1, 15, 0, 20))

    def test_wait_needs_var0(self):
        s = Script().cmd('B', 10, 30)
        self.assertEqual(C.trace(s.bytes()).length, 0)

    def test_loop_counts_from_code(self):
        # v10 counts to 3 with a wait each pass: jmp targets are relative to the code (after the 16-byte header)
        s = Script().set(0, -1)                      # code offset 0
        loop = len(s.code)
        s.set(10, 1, sub=1).cmd('B', 10, 5).skip(10, 3).jmp(loop)
        self.assertEqual(C.trace(s.bytes()).length, 15)


class Motion(unittest.TestCase):
    def params(self, **kw):
        p = [0] * C.NVARS
        for i in range(3):
            p[C.V_SCALE + i] = p[C.V_SCALE_END + i] = 4096
        for k, v in kw.items():
            if isinstance(v, (tuple, list)):
                for i, x in enumerate(v):
                    p[getattr(C, 'V_' + k.upper()) + i] = x
            else:
                p[getattr(C, 'V_' + k.upper())] = v
        return p

    def test_linear_and_snap(self):
        p = self.params(start=(0, 0, 0), end=(0, 0, -100), speed=10, motion=12)       # 12: snap and freeze
        self.assertEqual([round(x) for x in C.motion_at(p, 5)[0]], [0, 0, -50])
        self.assertEqual([round(x) for x in C.motion_at(p, 50)[0]], [0, 0, -100])

    def test_end_rule(self):
        p = self.params(start=(0, 0, 0), end=(100, 0, 0), speed=10, motion=13)       # 13: dies on arrival
        self.assertFalse(C.motion_at(p, 5)[3])
        self.assertTrue(C.motion_at(p, 20)[3])

    def test_static(self):
        p = self.params(start=(5, 6, 7), end=(100, 0, 0), speed=10, motion=0)
        self.assertEqual(C.motion_at(p, 9)[0], [5, 6, 7])

    def test_scale_clamps(self):
        p = self.params(scale=(4096,) * 3, scale_end=(8192,) * 3, scale_v=(1024,) * 3)
        self.assertEqual(C.motion_at(p, 2)[2], [1.5] * 3)
        self.assertEqual(C.motion_at(p, 100)[2], [2.0] * 3)


class Sprites(unittest.TestCase):
    def sheet(self, n=4, loop=-1, dur=3):
        d = b'sheet.tim'.ljust(16, b'\0') + struct.pack('<IIhH4H', 1, n, loop, 0, 368, 112, 320, 0)
        for i in range(n):
            d += struct.pack('<I4B2HHHhh', dur, 16 * i, 16 * i + 15, 0, 15, 16, 16, 1, 0x80, 0, 0)
        return d

    def test_parse(self):
        s = C.parse_sprite(self.sheet())
        self.assertTrue(s.loop)
        self.assertEqual([(f.u, f.w, f.ticks) for f in s.frames], [(0, 16, 3), (16, 16, 3), (32, 16, 3), (48, 16, 3)])

    def test_flip_frame_loops_and_holds(self):
        s = C.parse_sprite(self.sheet())
        self.assertEqual([C._flip_frame(s, t, 4) for t in (0, 3, 6, 9, 12)], [0, 1, 2, 3, 0])
        self.assertEqual([C._flip_frame(s, t, 2) for t in (0, 3, 6, 9)], [0, 0, 1, 1])
        once = C.parse_sprite(self.sheet(loop=0))
        self.assertEqual(C._flip_frame(once, 100, 4), 3)

    def test_tint(self):
        pal = [0, 31, 31 << 5]
        self.assertEqual(C.tint(pal, [128, 128, 128], False), pal)
        self.assertEqual(C.tint(pal, [64, 128, 128], True), [0, 15 | 0x8000, (31 << 5) | 0x8000])


class Unshear(unittest.TestCase):
    def test_keeps_rotation_scale(self):
        m = [[0, -2, 0], [1, 0, 0], [0, 0, 3]]
        self.assertEqual([[round(x, 6) for x in r] for r in C.unshear(m)], m)

    def test_removes_shear(self):
        u = C.unshear([[1, 0.5, 0], [0, 1, 0], [0, 0, 1]])
        cols = [[u[r][c] for r in range(3)] for c in range(3)]
        self.assertAlmostEqual(sum(a * b for a, b in zip(cols[0], cols[1])), 0, places=6)


class Sampling(unittest.TestCase):
    def test_fits(self):
        self.assertEqual(dcbefe.sample(10, 20, 60), (list(range(10, 20)), 1.0))

    def test_compresses(self):
        steps, k = dcbefe.sample(0, 120, 60)
        self.assertEqual((len(steps), steps[:3], k), (60, [0, 2, 4], 2.0))


def synthetic_pack(model_id=7):
    """A pack with one 4bpp sheet and a one-quad model built through the sprite path."""
    tim = C.Tim(1, 4, (0, 0), [[0x7fff] * 16], (320, 0), [[0x1111] * 16 for _ in range(64)])
    return C.Pack(1, {}, {1: tim}, {}, {})


def picture(boxes, size=(64, 40)):
    from tools.image import Image, ImageDraw
    im = Image.new('RGB', size, dcbefe.BG)
    d = ImageDraw.Draw(im)
    d.line((5, 10, 5, 39), fill=dcbefe.POST)
    for b in boxes:
        d.rectangle(b, fill=(250, 200, 60))
    return im


class Fidelity(unittest.TestCase):
    def moving(self, n, shift=0):
        return [picture([(10 + k + shift, 10, 20 + k + shift, 20)]) for k in range(n)]

    def test_same_passes(self):
        r = dcbefe.fidelity(self.moving(30), self.moving(15))
        self.assertTrue(r['passed'], r)

    def test_empty_fails(self):
        r = dcbefe.fidelity(self.moving(30), [picture([]) for _ in range(15)])
        self.assertFalse(r['passed'])
        self.assertIn('area', r['failed'])

    def test_dropped_part_fails(self):
        orig = [picture([(10, 10, 20, 20)]) for _ in range(10)] + [picture([(30, 5, 60, 35)]) for _ in range(10)]
        conv = [picture([(10, 10, 20, 20)]) for _ in range(10)] + [picture([]) for _ in range(10)]
        self.assertFalse(dcbefe.fidelity(orig, conv)['passed'])

    def test_elsewhere_fails(self):
        orig = [picture([(2, 2, 12, 12)]) for _ in range(10)]
        conv = [picture([(45, 25, 60, 38)]) for _ in range(10)]
        self.assertIn('box', dcbefe.fidelity(orig, conv)['failed'])

    def test_posts_ignored(self):
        self.assertEqual(dcbefe.lit(picture([])), [])


class Effect(unittest.TestCase):
    def test_sprite_object_converts(self):
        s = Script()
        s.set(C.V_RECT, 320).set(C.V_RECT + 1, 0).set(C.V_RECT + 2, 32).set(C.V_RECT + 3, 32)
        for i in range(3):
            s.set(C.V_RGB + i, 128).set(C.V_SCALE + i, 4096).set(C.V_SCALE_END + i, 4096)
        s.set(C.V_START + 1, -500).set(C.V_END + 1, -500).set(C.V_END + 2, -2000).set(C.V_SPEED, 100)
        s.set(C.V_MOTION, 11)
        s.cmd('C', 0, 1, 1).cmd('B', 8, 1).set(0, -1).cmd('B', 10, 20)
        tr = C.trace(s.bytes())
        pack = synthetic_pack()
        steps = list(range(0, 20))
        e = C.to_effect(tr, [pack], steps, vram_tims=[(pack.tims[1], 0, 0)])
        self.assertEqual(e._drawn.sprites, 1)
        self.assertEqual(len(e.frames), 20)
        table = struct.pack('<hhhhh', 0, 0, 0, 0, 0) + struct.pack('<hhhhh', -1, 0, 0, 0, 0)
        chunk, info = dw2efe.convert_skill([(1, e)], [], table, dcbefe.EFFECT_ID, dcbefe.SCALE)
        self.assertLessEqual(len(chunk), 0x5000)
        self.assertGreater(info['prims'], 0)


if __name__ == '__main__':
    unittest.main()
