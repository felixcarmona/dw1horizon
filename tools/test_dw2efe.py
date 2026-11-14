"""tools/dw2efe.py on small made-up DW2 effects (no disc data): a flat ring that charges and a dart that flies,
checked by layout, by disassembly and by running the chunk's scripts in tools/efesim.py."""
import math
import os
import struct
import unittest

from tools import dw2effect as D
from tools import dw2efe as C
from tools import efecheck
from tools import efescript
from tools import efesim as S

ONE = 4096
TYPE = 5
TABLE = struct.pack('<5h', TYPE, 5, 40, -30, 0) + struct.pack('<5h', -1, 0, 0, 0, 0)


def key(scale=(1, 1, 1), t=(0, 0, 0), yaw=0.0):
    c, s = math.cos(yaw), math.sin(yaw)
    sx, sy, sz = scale
    m = (c * sx, 0, s * sz, 0, sy, 0, -s * sx, 0, c * sz)
    return tuple(int(round(x * ONE)) for x in m), tuple(t)


def tim(palettes=1, width=32):
    """A 4bpp texture: texels at (0, 0), palettes on the last row (one per 16 halfwords)."""
    rows = [[0] * width for _ in range(256)]
    for p in range(palettes):
        rows[255][16 * p:16 * p + 16] = [0] + [0x8000 | (i * 2) << 10 | (i + p) % 32 for i in range(1, 16)]
    for v in range(64):
        rows[v][:width] = [0x1111 * (1 + (v + x) % 3) for x in range(width)]
    flat = b''.join(struct.pack(f'<{width}H', *r) for r in rows)
    return struct.pack('<II', 0x10, 0) + struct.pack('<I4H', 12 + len(flat), 0, 0, width, 256) + flat


def prim(verts, size=8, pal=0, u=0):
    s = size - 1
    return D.Prim(tuple(verts), ((u, 0), (u + s, 0), (u, s), (u + s, s))[:len(verts)], 255 << 6 | pal, 1)


def effect(frames, keys, ring_prims=None, texture=None, moves=()):
    ring = D.Bone(-1, [(-100, -100, 0), (100, -100, 0), (-100, 100, 0), (100, 100, 0)],
                  ring_prims or [prim((0, 1, 2, 3))])
    dart = D.Bone(-1, [(0, 0, -50), (-20, 0, 50), (20, 0, 50), (0, 20, 0)], [prim((0, 1, 2)), prim((0, 2, 3))])
    return D.Effect([ring, dart], texture or tim(), keys, frames, list(moves))


def cast(**kw):
    """Frames 0-29 the ring charges; from 30 the dart flies 400 a frame."""
    keys = [{0: key()}, {0: key((0, 0, 0))}]
    frames = [[0, 0 if f < 30 else f] for f in range(60)]
    for f in range(30, 60):
        keys[1][f] = key(t=(0, 0, -400 * (f - 29)))
    return effect(frames, keys, **kw)


def hit():
    keys = [{0: key((2, 2, 1))}, {0: key((0, 0, 0))}]
    return effect([[0, 0] for _ in range(30)], keys)


def stage(enemies=3):
    f = [None] * 10
    f[1] = S.Fighter(TYPE, (0, 0, 0), 0)
    for k in range(enemies):
        f[2 + k] = S.Fighter(TYPE, ((-1) ** k * 900 * ((k + 1) // 2), 0, -2700 - 300 * (k > 0)), 0x800)
    return f


def play(chunk, enemies=3):
    sim = S.Sim(chunk, stage(enemies), 1, 2)
    for _ in range(150):
        sim.step(reset_hits=True)
        if not sim.live():
            break
    return sim


class Convert(unittest.TestCase):
    def setUp(self):
        self.chunk, self.info = C.convert_skill([(1, cast())], [(1, hit())], TABLE, 0x17A, 0.5)
        self.h = efescript.header(self.chunk)

    def test_chunk_layout(self):
        h = self.h
        self.assertEqual(len(self.chunk), efescript.CHUNK)
        self.assertEqual(h['effectId'], 0x17A)
        self.assertTrue(h['subEffects'] < h['tmdStart'] < h['tmdEnd'] <= h['timStart'] < h['timEnd'])
        self.assertEqual(h['uvAnimsEnd'] - h['uvAnims'], 0x20 * self.info['objects'])
        self.assertEqual(h['tmdStart'] - h['subEffects'], 0x1c * h['numSubEffects'])
        tmd = self.chunk[0x34 + h['tmdStart']:]
        self.assertEqual(struct.unpack_from('<3I', tmd, 0), (0x41, 0, self.info['objects']))
        self.assertEqual(self.info['resident'], 0x34 + h['tmdEnd'])
        self.assertEqual(self.info['detail'], 'step 1 quant 1')

    def test_scripts_disassemble(self):
        text = efescript.listing(self.chunk)
        self.assertNotIn('.word', text)
        for op in ('drawTMDYXZ', 'addAttackObjectToTarget', 'checkTechCompatibility', 'playSound',
                   'faceTargetEntity'):
            self.assertIn(op, text)
        self.assertNotIn('applyBoxAttackHit', text)

    def test_projectile_hits_its_target_on_arrival(self):
        self.assertEqual(self.info['behaviour'], 'projectile')
        sim = play(self.chunk)
        self.assertEqual([i for _t, i, _p in sim.hits], [2])
        t = sim.hits[0][0]
        self.assertGreater(t, self.info['launch'])
        self.assertIn((self.info['launch'], 14), sim.sounds)
        # the hit objects play at the target, at mid height
        ring = [d for d in sim.draws if d[0] > t and d[4][2] < -2000]
        self.assertTrue(ring)
        self.assertEqual(sim.live(), 0)

    def test_area_hits_every_enemy(self):
        chunk, info = C.convert_skill([(1, cast())], [(1, hit())], TABLE, 0x17A, 0.5, area=True)
        self.assertEqual(info['behaviour'], 'projectile x target')
        sim = play(chunk)
        self.assertEqual(sorted(i for _t, i, _p in sim.hits), [2, 3, 4])
        sim = play(chunk, enemies=2)
        self.assertEqual(sorted(i for _t, i, _p in sim.hits), [2, 3])

    def test_hits_face_back_along_the_fighters_line(self):
        # DW2 turns every hit object half round in the battle's frame: the side enemies' bursts face the same
        # way as the middle one's, not the point their projectile came from
        burst = effect([[0, 0] for _ in range(30)], [{0: key()}, {0: key((0, 0, 0))}],
                       ring_prims=[prim((0, 1, 2, 3), u=8)])
        chunk, info = C.convert_skill([(1, cast())], [(1, burst)], TABLE, 0x17A, 0.5, area=True)
        sim = play(chunk)
        ids = {i for b in info['parts']['hit slot 1'].values() for i in b}
        yaws = {d[2][1] & 0xFFF for d in sim.draws if d[1] in ids}
        self.assertEqual(yaws, {0x800})

    def test_several_hits(self):
        chunk, info = C.convert_skill([(1, cast())], [(1, hit())], TABLE, 0x17A, 0.5, n_hits=3)
        sim = play(chunk)
        self.assertEqual([i for _t, i, _p in sim.hits], [2, 2, 2])
        self.assertEqual(len(info['hit_events']), 3)

    def test_melee_hits_at_the_target_without_a_traveller(self):
        keys = [{0: key()}, {0: key((0, 0, 0))}]
        chunk, info = C.convert_skill([(2, effect([[0, 0]] * 40, keys))], [(1, hit())], TABLE, 0x17A, 0.5)
        self.assertEqual(info['behaviour'], 'melee')
        sim = play(chunk)
        self.assertEqual([i for _t, i, _p in sim.hits], [2])
        self.assertEqual(sim.hits[0][0], info['hit_tick'])

    def test_support_technique_deals_no_damage(self):
        chunk, info = C.convert_skill([(1, cast())], [(1, hit())], TABLE, 0x17A, 0.5, self_target=True)
        self.assertEqual(info['behaviour'], 'buff')
        sim = play(chunk)
        self.assertEqual(sim.hits, [])
        late = [d for d in sim.draws if d[0] > info['cast_ticks'] - 2 and d[1] in (0, 1)]
        self.assertTrue(all(abs(d[4][2]) < 1000 for d in late))

    def test_several_cast_slots_and_no_hit_object(self):
        keys = [{0: key()}, {0: key((0, 0, 0))}]
        still = effect([[0, 0]] * 20, keys)
        chunk, info = C.convert_skill([(0, still), (1, cast()), (2, still)], [], TABLE, 0x17A, 0.5)
        sim = play(chunk)
        self.assertEqual([i for _t, i, _p in sim.hits], [2])

    def test_flat_parts_have_both_sides(self):
        # the ring is drawn from both sides, the dart (a solid) once; the hit's dart never shows and is left out,
        # and the hit's ring is the same card as the cast's
        self.assertEqual(self.info['prims'], 2 + 2)
        self.assertEqual(self.info['objects'], 2)                # the hit's ring is the cast's: one object

    def test_rotation_and_sideways_motion_convert(self):
        e = cast()
        for f in range(30, 60):
            e.keys[1][f] = key((1, 2, 1), t=(300, -50, -400 * (f - 29)), yaw=0.3)
        chunk, info = C.convert_skill([(1, e)], [(1, hit())], TABLE, 0x17A, 0.5)
        self.assertEqual(info['behaviour'], 'projectile')

    def test_shear_refused(self):
        e = cast()
        e.keys[1][45] = ((ONE, ONE, 0, 0, ONE, 0, 0, 0, ONE), (0, 0, -6000))
        with self.assertRaises(C.Unconvertible):
            C.convert_skill([(1, e)], [(1, hit())], TABLE, 0x17A, 0.5)

    def test_texture_halved(self):
        tim_at = 0x34 + self.h['timStart']
        _size, _x, _y, w, rows = struct.unpack_from('<I4H', self.chunk, tim_at + 8)
        self.assertEqual((w, rows), (16, 1))                    # one palette row: the one the prims use
        self.assertEqual(self.info['texture'], '4x4')           # 8 texels square, halved
        self.assertEqual(self.info['factors'], '2')

    def test_big_texture_reduced_to_the_strip(self):
        ring = [prim((0, 1, 2, 3), size=64, u=64 * k) for k in range(4)]
        chunk, info = C.convert_skill([(1, cast(ring_prims=ring, texture=tim(width=64)))], [], TABLE, 0x17A, 0.5)
        w, h = (int(x) for x in info['texture'].split('x'))
        self.assertLessEqual(w, 256)
        self.assertLessEqual(h, 32)
        self.assertGreaterEqual(min(int(f.rstrip('T')) for f in info['factors'].split(',')), 2)

    def test_palettes_reduced_to_six(self):
        ring = [prim((0, 1, 2, 3), pal=p) for p in range(9)]
        chunk, info = C.convert_skill([(1, cast(ring_prims=ring, texture=tim(palettes=9, width=160)))], [],
                                      TABLE, 0x17A, 0.5)
        self.assertEqual(info['palettes'], '9->6')

    def test_invisible_prims_left_out(self):
        texture = bytearray(tim())
        ring = [prim((0, 1, 2, 3)), prim((0, 1, 2, 3), u=24)]       # texels at u 24-31 use colour 0 only
        for v in range(8):
            struct.pack_into('<2H', texture, 20 + 2 * (32 * v + 6), 0, 0)
        chunk, info = C.convert_skill([(1, cast(ring_prims=ring, texture=bytes(texture)))], [], TABLE, 0x17A, 0.5)
        self.assertEqual(info['prims'], 2 + 2)

    def test_flipbook_becomes_a_uv_animation(self):
        move = D.TexMove((0, 0), (2, 8), [(0, 0), (2, 0), (4, 0)], 2, 2)
        chunk, info = C.convert_skill([(1, cast(moves=[move]))], [], TABLE, 0x17A, 0.5)
        self.assertEqual(info['flipbooks'], 2)                  # the ring's and the dart's prims use it
        sim = play(chunk)
        offsets = {d[5] for d in sim.draws if d[1] == 0}
        self.assertGreater(len(offsets), 1)

    def test_flipbook_used_in_part(self):
        # the ring's quad stops a row short of the flipbook's destination (8..15): it still shows the frames,
        # not what the destination holds before the first copy
        move = D.TexMove((0, 8), (2, 8), [(2, 0), (4, 0), (6, 0)], 2, 2)
        ring = [D.Prim((0, 1, 2, 3), ((0, 8), (7, 8), (0, 14), (7, 14)), 255 << 6, 1)]
        chunk, info = C.convert_skill([(1, cast(ring_prims=ring, moves=[move]))], [], TABLE, 0x17A, 0.5)
        self.assertEqual(info['flipbooks'], 1)
        sim = play(chunk)
        self.assertGreater(len({d[5] for d in sim.draws if d[1] == 0}), 1)

    def test_gradient_palette_made_blending(self):
        # a palette with no transparent and no blending colour: colour 0 turns transparent, the others blend
        image = [[0x5c00 + i for i in range(16)] + [0] * 16]
        cols = C.colours(image, 0)
        self.assertEqual(cols[0], 0)
        self.assertTrue(all(c & 0x8000 for c in cols[1:]))
        fire = [[0] + [0x8000 | i for i in range(1, 16)] + [0] * 16]
        self.assertEqual(C.colours(fire, 0), tuple(fire[0][:16]))

    def test_hit_scale(self):
        small, info = C.convert_skill([(1, cast())], [(1, hit())], TABLE, 0x17A, 0.5, hit_scale=0.25)
        self.assertEqual(info['prims'], self.info['prims'])
        self.assertNotEqual(small, self.chunk)

    def test_first_form_still_converts(self):
        chunk, info = C.convert(cast(), hit(), TABLE, 0x17A, 0.5, reach=3000)
        self.assertEqual(chunk, self.chunk)


DW2_IMAGE = os.environ.get('DW2_IMAGE', '')


@unittest.skipUnless(os.path.isfile(DW2_IMAGE), 'needs the Digimon World 2 disc (DW2_IMAGE)')
class Fidelity(unittest.TestCase):
    """tools/efecheck.py on Metal Fireball (a ball and a ring, then a burst at the target): the conversion shows
    what DW2 shows; one that loses the burst or draws everything far smaller fails."""

    @classmethod
    def setUpClass(cls):
        disc = D.Disc(DW2_IMAGE)

        def load(m, a):
            return D.parse_effect(*(disc.image.read(*disc.files['AAA/4.AAA/EFFECT/' + n]) for n in (m, a)))
        cls.casts = [(1, load('EFFEWA/MEWA0200.BIN', 'EFFEWA/AEWA0200.BIN'))]
        cls.hits = [(1, load('EFFEWD/MEWD0100.BIN', 'EFFEWD/AEWD0100.BIN'))]

    def fidelity(self, casts, hits, scale=0.266, hit_scale=0.1, claimed=None):
        chunk, info = C.convert_skill(casts, hits, TABLE, 0x17A, scale, hit_scale=hit_scale)
        placed = efecheck.place(self.casts, self.hits)
        return efecheck.check(placed, chunk, info, TABLE, *(claimed or (scale, hit_scale)), size=(96, 60))

    def test_conversion_passes(self):
        rep = self.fidelity(self.casts, self.hits)
        self.assertEqual(rep['fails'], [])
        for phase in rep['phases'].values():
            self.assertGreater(phase['energy'], 0.7)
            self.assertGreater(phase['box'], 0.7)

    def test_lost_hit_fails(self):
        rep = self.fidelity(self.casts, [])
        self.assertTrue(any(f.startswith('hit: mostly empty') for f in rep['fails']), rep['fails'])
        self.assertTrue(any('hit slot 1 bone' in f and 'dropped' in f for f in rep['fails']), rep['fails'])
        self.assertFalse(any(f.startswith('cast') for f in rep['fails']), rep['fails'])

    def test_shrunk_conversion_fails(self):
        rep = self.fidelity(self.casts, self.hits, 0.06, 0.025, claimed=(0.266, 0.1))
        self.assertTrue(any('box collapsed' in f for f in rep['fails']), rep['fails'])
        self.assertTrue(any('mostly empty' in f for f in rep['fails']), rep['fails'])


if __name__ == '__main__':
    unittest.main()
