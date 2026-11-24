"""The arenas of the cups after the original's: one slot per arena after the banners in STDDAT/GRADE/NEWCUPS.BIN.

    python3 -m tools.cup_arenas preview NAME OUT.png        # a picture of an arena from the fight camera (needs Pillow)

A slot is TIM_SECTORS of textures then TMD_SECTORS of model, read by STD_loadArenaAssets for a cup whose arena is not
the File City one (STD_NEW_CUP_ARENA). Both stay within what the File City arena (STDDAT/T_TOGI) takes: its textures
go to the same video memory and its model to the same heap block, so a new arena costs no memory.

The model is ours, made here: a round floor with a medallion at the centre, a low wall round it, eight pillars and a
cliff with a dark sky. Its three objects play the parts of the File City arena's, so the game draws it with that
arena's renderer: object 0 the floor and the wall (drawn finer in the champion scene), object 1 what stands above
(the File City arena's lights; here the pillars), object 2 everything round it.

The textures are the generator's art (content/arenas/<name>/), kept as three pictures that share one palette of 256
colours, the size of the places the File City arena's textures take in video memory:
    a.png 256x240  floor tile (0,0)-(127,127), medallion (128,0)-(255,127), wall (0,128)-(255,239)
    b.png 256x120  cliff
    c.png 128x120  pillar
No Pillow, no downloads: the player's build packs them too.
"""
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, 'tools')):
    if path not in sys.path:
        sys.path.insert(0, path)
ART = os.path.join(ROOT, 'content', 'arenas')
SECTOR = 2048
TIM_SECTORS = 54                # STD_ARENA_TIM_SECTORS: T_TOGI.TIM is 109376 bytes
TMD_SECTORS = 13                # STD_ARENA_TMD_SECTORS: the heap block T_TOGI.TMD takes (26264 bytes, rounded)
SLOT_SECTORS = TIM_SECTORS + TMD_SECTORS
ARENAS = ['dragons-roar']       # slot order; STD_NEW_CUP_ARENA names the slot of each cup

# Video memory: the rectangles T_TOGI.TIM fills (x in 16-bit units), all 8-bit textures on one palette.
PAGES = {'a': ((512, 0), (256, 240)), 'b': ((640, 0), (256, 120)), 'c': ((640, 120), (128, 120))}
CLUT_XY = (512, 254)
TSB = {'a': 8 | 0x80, 'b': 10 | 0x80, 'c': 10 | 0x80}       # texture page, 8-bit
CBA = (CLUT_XY[1] << 6) | (CLUT_XY[0] >> 4)
# Regions (page, u0, v0, u1, v1), inclusive texel bounds.
FLOOR = ('a', 0, 0, 127, 127)
MEDALLION = ('a', 128, 0, 255, 127)
WALL = ('a', 0, 128, 255, 239)
CLIFF = ('b', 0, 0, 255, 119)
PILLAR = ('c', 0, 120, 127, 239)

# Shape (PlayStation units, y down, the floor at 0). The fight's area and collision are the original's (B_TOGI.ATR):
# the floor reaches the File City arena's cage at 3120.
SEGMENTS = 24
MEDALLION_R = 1000
FLOOR_RINGS = [1000, 1750, 2450, 3260]       # the last ring passes under the wall, so no gap shows at its foot
WALL_R, WALL_H, WALL_T = 3120, 560, 200
TERRACE_R = 4300
PILLARS, PILLAR_R, PILLAR_W, PILLAR_H = 8, 3720, 380, 3000
CLIFF_SEGMENTS, CLIFF_TIERS, CLIFF_H = 32, 3, 3300
SKY_TOP = -5200
SKY = [(72, 66, 70), (36, 33, 38), (14, 13, 18)]   # the vault's shade (128 = as drawn): cliff top, middle, top


class Mesh:
    def __init__(self):
        self.verts, self.index, self.prims = [], {}, []

    def v(self, x, y, z):
        key = (int(round(x)), int(round(y)), int(round(z)))
        if key not in self.index:
            self.index[key] = len(self.verts)
            self.verts.append(key)
        return self.index[key]

    def quad(self, p, uv, region, color=(128, 128, 128), toward=None):
        """p: four points in the PlayStation quad order (0 1 / 2 3); the side facing the point `toward` is drawn.
        color: one colour, or one per corner (the texture is multiplied by it, 128 = as drawn)."""
        page = region[0]
        colors = list(color) if isinstance(color[0], (tuple, list)) else [color] * 4
        p, both = facing(p, list(zip(uv, colors)), toward)
        uv, colors = [t[0] for t in both], [t[1] for t in both]
        self.prims.append(dict(mode=0x3D, flag=1, uv=[tuple(int(round(c)) for c in t) for t in uv], cba=CBA,
                               tsb=TSB[page], colors=[tuple(c) + (0,) for c in colors], verts=[self.v(*q) for q in p]))

    def tri(self, p, uv, region, color=(128, 128, 128), toward=None):
        page = region[0]
        p, uv = facing(p, uv, toward)
        self.prims.append(dict(mode=0x35, flag=1, uv=[tuple(int(round(c)) for c in t) for t in uv], cba=CBA,
                               tsb=TSB[page], colors=[tuple(color) + (0,)] * 3, verts=[self.v(*q) for q in p]))


def facing(p, extra, toward):
    """The quad or triangle with its order swapped if needed so that the side facing `toward` is the one drawn: the
    drawn side is the one (v1-v0)x(v2-v0) points away from (as in the File City arena's floor and cage)."""
    if toward is None:
        return p, extra
    e1 = [p[1][i] - p[0][i] for i in range(3)]
    e2 = [p[2][i] - p[0][i] for i in range(3)]
    n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
    c = [sum(q[i] for q in p) / len(p) for i in range(3)]
    if sum(n[i] * (toward[i] - c[i]) for i in range(3)) <= 0:
        return p, extra
    if len(p) == 4:
        order = [1, 0, 3, 2]
    else:
        order = [0, 2, 1]
    return [p[i] for i in order], [extra[i] for i in order]


ABOVE = (0, -20000, 0)
CENTRE = (0, -800, 0)


def ring(r, k, n, y=0):
    a = 2 * math.pi * k / n
    return (r * math.sin(a), y, r * math.cos(a))


def floor_object():
    m = Mesh()
    _, u0, v0, u1, v1 = MEDALLION
    cu, cv, ru, rv = (u0 + u1) / 2, (v0 + v1) / 2, (u1 - u0) / 2, (v1 - v0) / 2
    for k in range(SEGMENTS):
        a, b = ring(MEDALLION_R, k, SEGMENTS), ring(MEDALLION_R, k + 1, SEGMENTS)
        uv = lambda p: (cu + p[0] / MEDALLION_R * ru, cv + p[2] / MEDALLION_R * rv)
        m.tri([(0, 0, 0), b, a], [uv((0, 0, 0)), uv(b), uv(a)], MEDALLION, toward=ABOVE)
    _, u0, v0, u1, v1 = FLOOR
    for r0, r1 in zip(FLOOR_RINGS, FLOOR_RINGS[1:]):
        for k in range(SEGMENTS):
            p = [ring(r0, k, SEGMENTS), ring(r0, k + 1, SEGMENTS), ring(r1, k, SEGMENTS), ring(r1, k + 1, SEGMENTS)]
            m.quad([p[1], p[0], p[3], p[2]], [(u0, v0), (u1, v0), (u0, v1), (u1, v1)], FLOOR, toward=ABOVE)
    _, u0, v0, u1, v1 = WALL
    top = v0 + 14
    for k in range(SEGMENTS):
        a0, a1 = ring(WALL_R, k, SEGMENTS), ring(WALL_R, k + 1, SEGMENTS)
        t0, t1 = ring(WALL_R, k, SEGMENTS, -WALL_H), ring(WALL_R, k + 1, SEGMENTS, -WALL_H)
        m.quad([t0, t1, a0, a1], [(u0, top), (u1, top), (u0, v1), (u1, v1)], WALL, toward=CENTRE)   # the inner face
        o0, o1 = ring(WALL_R + WALL_T, k, SEGMENTS, -WALL_H), ring(WALL_R + WALL_T, k + 1, SEGMENTS, -WALL_H)
        m.quad([o0, o1, t0, t1], [(u0, v0), (u1, v0), (u0, top), (u1, top)], WALL, toward=ABOVE)    # the capstones
    return m


def pillar_object():
    m = Mesh()
    _, u0, v0, u1, v1 = PILLAR
    h = PILLAR_W / 2
    for k in range(PILLARS):
        a = 2 * math.pi * (k + .5) / PILLARS
        cx, cz = PILLAR_R * math.sin(a), PILLAR_R * math.cos(a)
        corners = [(cx + dx * math.cos(a) + dz * math.sin(a), cz - dx * math.sin(a) + dz * math.cos(a))
                   for dx, dz in ((-h, -h), (h, -h), (h, h), (-h, h))]
        tiers = 3
        for f in range(4):
            (x0, z0), (x1, z1) = corners[f], corners[(f + 1) % 4]
            for t in range(tiers):
                ya, yb = -PILLAR_H * (t + 1) / tiers, -PILLAR_H * t / tiers
                out = (2 * (x0 + x1) / 2 - cx, 0, 2 * (z0 + z1) / 2 - cz)
                m.quad([(x0, ya, z0), (x1, ya, z1), (x0, yb, z0), (x1, yb, z1)],
                       [(u0, v0), (u1, v0), (u0, v1), (u1, v1)], PILLAR, toward=(out[0], (ya + yb) / 2, out[2]))
        top = [(x, -PILLAR_H, z) for x, z in corners]
        m.quad([top[0], top[1], top[3], top[2]], [(u0, v0), (u1, v0), (u0, v0 + 20), (u1, v0 + 20)], PILLAR, toward=ABOVE)
    return m


def surround_object():
    m = Mesh()
    _, u0, v0, u1, v1 = FLOOR
    for k in range(SEGMENTS):
        p = [ring(FLOOR_RINGS[-1] - 10, k, SEGMENTS), ring(FLOOR_RINGS[-1] - 10, k + 1, SEGMENTS),
             ring(TERRACE_R + 60, k, SEGMENTS), ring(TERRACE_R + 60, k + 1, SEGMENTS)]
        m.quad([p[1], p[0], p[3], p[2]], [(u0, v0), (u1, v0), (u0, v1), (u1, v1)], FLOOR, (96, 96, 96), toward=ABOVE)
    _, u0, v0, u1, v1 = CLIFF
    n = CLIFF_SEGMENTS
    for k in range(n):
        for t in range(CLIFF_TIERS):
            ya, yb = -CLIFF_H * (t + 1) / CLIFF_TIERS, -CLIFF_H * t / CLIFF_TIERS + (60 if t == 0 else 0)
            p0, p1 = ring(TERRACE_R, k, n, ya), ring(TERRACE_R, k + 1, n, ya)
            q0, q1 = ring(TERRACE_R, k, n, yb), ring(TERRACE_R, k + 1, n, yb)
            # the picture once from the foot to the top of the cliff, a quarter of its width per segment
            ua, ub = u0 + (u1 + 1 - u0) * (k % 4) // 4, u0 + (u1 + 1 - u0) * (k % 4 + 1) // 4 - 1
            va, vb = v1 - (v1 - v0) * (t + 1) // CLIFF_TIERS, v1 - (v1 - v0) * t // CLIFF_TIERS
            m.quad([p0, p1, q0, q1], [(ua, va), (ub, va), (ua, vb), (ub, vb)], CLIFF, toward=CENTRE)
    # The dark vault above the cliff: the rough top of the cliff picture, darker towards the top. Textured like
    # everything else: of the untextured kinds the game's GsSortObject4 has no working handler.
    mid_r, mid_y = TERRACE_R * .8, (-CLIFF_H + SKY_TOP) / 2 - 300
    for k in range(n):
        ua, ub = u0 + (u1 + 1 - u0) * (k % 4) // 4, u0 + (u1 + 1 - u0) * (k % 4 + 1) // 4 - 1
        uv = [(ua, v0), (ub, v0), (ua, v0 + 40), (ub, v0 + 40)]
        a0, a1 = ring(TERRACE_R, k, n, -CLIFF_H), ring(TERRACE_R, k + 1, n, -CLIFF_H)
        b0, b1 = ring(mid_r, k, n, mid_y), ring(mid_r, k + 1, n, mid_y)
        m.quad([b0, b1, a0, a1], uv, CLIFF, [SKY[1], SKY[1], SKY[0], SKY[0]], toward=CENTRE)
        c0, c1 = ring(TERRACE_R * .3, k, n, SKY_TOP + 200), ring(TERRACE_R * .3, k + 1, n, SKY_TOP + 200)
        m.quad([c0, c1, b0, b1], uv, CLIFF, [SKY[2], SKY[2], SKY[1], SKY[1]], toward=CENTRE)
        top = (0, SKY_TOP, 0)
        m.quad([c0, c1, top, top], uv, CLIFF, [SKY[2]] * 4, toward=CENTRE)
    return m


# Every polygon is unlit (flag 1) and textured: the kinds the File City arena uses, which GsSortObject4 draws.
def tmd():
    import mmd
    t = mmd.TMD()
    for mesh in (floor_object(), pillar_object(), surround_object()):
        ob = mmd.TMDObject()
        ob.vert_start, ob.nvert = len(t.verts), len(mesh.verts)
        t.verts += [v + (0,) for v in mesh.verts]
        ob.norm_start, ob.nnorm = 0, 0
        for p in mesh.prims:
            p = dict(p)
            if p['flag'] != 1 or not p['mode'] & 4:
                raise ValueError(f"a polygon of mode {p['mode']:#x}, flag {p['flag']}: the game has no handler for it")
            p.setdefault('uv', [])
            p.setdefault('cba', 0)
            p.setdefault('tsb', 0)
            ob.prims.append(mmd.Prim.encode(p))
        t.objects.append(ob)
    t.norms = [(0, -4096, 0, 0)]
    data = t.build()
    if len(data) > TMD_SECTORS * SECTOR:
        raise ValueError(f'the arena model is {len(data)} bytes, more than the {TMD_SECTORS * SECTOR} it may take')
    return data


def tim(name):
    """The three textures as TIMs at the File City arena's places, the palette with the first."""
    import dwmap
    out, palette = b'', None
    for i, page in enumerate('abc'):
        w, h, mode, rows, colours = dwmap.png_read(os.path.join(ART, name, page + '.png'))
        if (w, h, mode) != (PAGES[page][1][0], PAGES[page][1][1], 'P'):
            raise ValueError(f'{name}/{page}.png: a {w}x{h} {mode} picture, it must be {PAGES[page][1]} with a palette')
        colours = (list(colours) + [(0, 0, 0)] * 256)[:256]
        if palette is None:
            palette = colours
        elif colours != palette:
            raise ValueError(f'{name}/{page}.png: the three pictures must share one palette')
        (x, y), _ = PAGES[page]
        if i == 0:
            clut = [max(1, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in palette]   # never 0: opaque
            out += struct.pack('<II', 0x10, 9) + struct.pack('<IHHHH', 12 + 512, *CLUT_XY, 256, 1)
            out += struct.pack('<256H', *clut)
        else:
            out += struct.pack('<II', 0x10, 1)
        out += struct.pack('<IHHHH', 12 + w * h, x, y, w // 2, h) + b''.join(bytes(row) for row in rows)
    if len(out) > TIM_SECTORS * SECTOR:
        raise ValueError(f'the arena textures are {len(out)} bytes, more than the {TIM_SECTORS * SECTOR} they may take')
    return out


def slots():
    """Every arena's slot, in ARENAS order."""
    return b''.join(tim(n).ljust(TIM_SECTORS * SECTOR, b'\0') + tmd().ljust(TMD_SECTORS * SECTOR, b'\0')
                    for n in ARENAS)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'size':
        print(len(tmd()), 'bytes of model')
    else:
        sys.exit(__doc__)
