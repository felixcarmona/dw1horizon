#!/usr/bin/env python3
"""Digimon World 2003 / Digimon World 3 battle sprite effects: decode and render them to PNG frames.

A sprite effect is a flat, animated picture drawn by a technique script (op 3, `sprite mode id x y z`).
The fight overlay (FIGHTSTG.PRO) has a sprite table {i16 id, i16 pack, i16 section, i16 file} and a
pack table (16-byte records) that says, per pack, where its pieces are. A pack is one disc file
(E000COM1..4 are shared, E###XXXX.BIN belong to one Digimon) made of "sections" (the u32 offset
table that the dw3 package's section splitter reads). Everything below was read from the data and
checked by looking at the rendered pictures; nothing is taken from the disc into the repository.

Pack table record (u16 words): [0] section index of the texture, [2] section index of the frame
table, [3] file index, [4] VRAM x of the texture page (halfwords). E000COM1..4 have no texture
section: their pages are the RLEN blocks of F000COM1..4.BIN (COM1 has two pages, 320 and 384).

Texture: an RLEN-compressed 16-bit TIM of 64 x 256 halfwords = one 256 x 256 page of 4-bit pixels,
whose palettes (16 halfwords each) are stored in its bottom rows. A texture section is a u32 offset
table (0 ends it) of RLEN blocks. Several pages sit side by side: a rect's u >= 256 is on page u // 256.
Colour 0x0000 is transparent; bit 15 of a colour is the PlayStation semi-transparency flag.

Frame table section (one per pack; a sprite section never contains one): u32 offsets
  [0] rects: 14-byte records u16 {u, v, w, h, clut_x, clut_y, 0}: a pixel rectangle of the page and the
      palette (halfword position inside the page) used to draw it.
  [1] frame ids: one byte per frame record, ending in 0xFF; the id is what animations name.
  [2..] one record per frame: u16 {count, a, b}, then count parts u16 {rect, x, y}. The part's x, y is
      the top-left corner relative to the sprite's centre. a is a palette row offset added to the
      block's; b is the blend: -1 solid, 0 to 3 the PlayStation's semi-transparency rate (half, add,
      subtract, add a quarter). Each part is its own primitive, the last drawn on top.
  A rect's word [6] is its colour depth: 0 is 4-bit. Colour 0x8000 is solid black; only 0x0000 is clear.

Sprite section (what the sprite table's section number names): u32 offsets of "blocks" (0 ends the
table). Each block is an independent layer that starts with the sprite. Block = 12 u16 header,
then `count` entries of `popcount(channels)` u16, then 0x00FF:
  [0] channels: bit mask; one u16 per set bit in each entry, in bit order. Bit i replaces header word
      3 + i: 0 frame id, 1 palette row offset, 2 x, 3 y (pixels), 4 scale x, 5 scale y (4096 = 1.0),
      6, 7, 8 turn about x, y, z (4096 = a full turn; about x and y only narrows, depth is dropped).
  [1] u16 per entry; always popcount(channels).  [2] number of entries, one per 60 Hz tick.
  [3] frame id  [4] palette row offset  [5] x  [6] y  [7] [8] scale x, y  [9] [10] [11] turn x, y, z.
A block with a scale of 0 is not drawn. Times, as the technique script's waits, are 1/60 s ticks
(fight overlay 0x80083A54); the pictures here are drawn every second tick, at 30 fps.

The technique script places the sprite (op 3: id, x, y, z). z = 32767 draws it in screen space in front
of everything and z = -1 behind it, x and y in pixels from the screen's middle; any other z is a field
position, projected again every frame. The size in pixels does not change with distance.
"""
import argparse
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FPS = 30                # the pictures render() makes
TICKS = 60              # block entries per second: one per 1/60 s of game time (the script's waits count the same)
CHANNELS = ('frame', 'pal', 'x', 'y', 'sx', 'sy', 'rx', 'ry', 'rot')     # channel bit i replaces header word 3 + i
FRAME_TABLE_END = 0xFF


def _rlen(data, offset):
    """The game's RLEN block (b'RLEN', u32 size, then runs: 0x00-0x7F literal bytes, 0x80+ n repeats)."""
    if data[offset:offset + 4] != b'RLEN':
        raise ValueError('not RLEN')
    size = struct.unpack_from('<I', data, offset + 4)[0]
    out = bytearray()
    p = offset + 8
    while len(out) < size:
        op = data[p]
        p += 1
        if op < 0x80:
            out += data[p:p + op]
            p += op
        else:
            out += bytes([data[p]]) * (op - 0x80)
            p += 1
    return bytes(out)


def _offsets(section):
    """The u32 offset table at the start of a section: its entries up to the first 0 (the first offset is
    the table's own length in bytes)."""
    out = []
    end = struct.unpack_from('<I', section, 0)[0]
    for q in range(0, min(end, len(section)), 4):
        o = struct.unpack_from('<I', section, q)[0]
        if o == 0:
            break
        out.append(o)
    return out


class Page:
    """A 256 x 256 page of 4-bit indices and its palettes (the halfword rows of the same TIM)."""

    def __init__(self, tim):
        _m, flags = struct.unpack_from('<2I', tim, 0)
        _s, _x, _y, w, h = struct.unpack_from('<I4H', tim, 8)
        if flags & 7 != 2 or (w, h) != (64, 256):
            raise ValueError('unexpected page TIM %r' % ((flags, w, h),))
        self.hw = np.frombuffer(tim, '<u2', w * h, 20).reshape(h, w)
        raw = self.hw.view(np.uint8).reshape(h, w * 2)
        self.idx = np.empty((h, w * 4), np.uint8)
        self.idx[:, 0::2], self.idx[:, 1::2] = raw & 15, raw >> 4

    def crop(self, u, v, w, h, clut_x, clut_y, stp_alpha=255):
        """RGBA pixels of a rect with the palette at (clut_x, clut_y) of this page; colours with the
        semi-transparency bit get alpha `stp_alpha` (a marker for blending renderers)."""
        pal = np.zeros((16, 4), np.uint8)
        for i, c in enumerate(self.hw[clut_y, clut_x:clut_x + 16].tolist()):
            if c & 0x7FFF:
                pal[i] = ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31,
                          stp_alpha if c & 0x8000 else 255)
            elif c:                         # 0x8000: opaque black (only 0x0000 is transparent)
                pal[i] = (0, 0, 0, 255)
        return pal[self.idx[v:v + h, u:u + w]]


def _pages(section):
    """The pages of a texture section: a plain RLEN block (F000COM*) or an offset table of RLEN blocks."""
    if section[:4] == b'RLEN':
        return [Page(_rlen(section, 0))]
    return [Page(_rlen(section, o)) for o in _offsets(section)]


class Block:
    def __init__(self, data):
        h = struct.unpack_from('<12H', data, 0)
        self.channels, self.stride, self.count, self.base_frame, self.pal = h[:5]
        self.x, self.y = struct.unpack_from('<2h', data, 10)
        self.sx, self.sy, self.rx, self.ry, self.rot = h[7], h[8], h[9], h[10], h[11]
        self.bits = [b for b in range(9) if self.channels >> b & 1]
        self.entries = []
        for k in range(self.count):
            vals = struct.unpack_from('<%dH' % len(self.bits), data, 24 + 2 * len(self.bits) * k)
            self.entries.append(dict(zip((CHANNELS[b] for b in self.bits), vals)))

    def at(self, tick):
        """{frame, pal, x, y, sx, sy, rx, ry, rot} at a tick (1/60 s), or None once the block has ended or
        while it is not drawn (a zero scale). sx, sy signed, 4096 = 1.0; rx, ry, rot 4096 = a full turn."""
        if tick >= self.count:
            return None
        e = self.entries[tick]
        s16 = lambda v: v - 65536 if v >= 32768 else v      # noqa: E731
        st = {'frame': e.get('frame', self.base_frame), 'pal': e.get('pal', self.pal),
              'x': s16(e['x']) if 'x' in e else self.x, 'y': s16(e['y']) if 'y' in e else self.y,
              'sx': s16(e.get('sx', self.sx)), 'sy': s16(e.get('sy', self.sy)),
              'rx': e.get('rx', self.rx), 'ry': e.get('ry', self.ry), 'rot': e.get('rot', self.rot)}
        return None if st['sx'] == 0 or st['sy'] == 0 else st

    def flat_scale(self, st):
        """The on-screen scale (x, y): the engine drops z after turning about x and y, so those turns only
        foreshorten."""
        return (st['sx'] / 4096 * math.cos(st['ry'] * 2 * math.pi / 4096),
                st['sy'] / 4096 * math.cos(st['rx'] * 2 * math.pi / 4096))


class Pack:
    """One effect file: its frame table and pages. Sprite sections come from `sprite(section)`."""

    def __init__(self, disc, name, tex_section, table_section, com_textures=None):
        from tools import dw3effect as X
        self.name = name
        self.sections = X.sections_of(disc.read(name))
        if com_textures:
            self.pages = _pages(X.sections_of(disc.read(com_textures))[0])
            for s in X.sections_of(disc.read(com_textures))[1:]:
                if len(s) > 8:
                    self.pages += _pages(s)
        else:
            self.pages = _pages(self.sections[tex_section])
        t = self.sections[table_section]
        offs = _offsets(t)
        n = (offs[1] - offs[0]) // 14
        self.rects = [struct.unpack_from('<7H', t, offs[0] + 14 * i) for i in range(n)]
        ids = t[offs[1]:offs[2]]
        ids = list(ids[:ids.index(FRAME_TABLE_END)])
        self.frames = {}
        for k, fid in enumerate(ids):
            o = offs[2 + k]
            count, a, b = struct.unpack_from('<3H', t, o)
            parts = [struct.unpack_from('<Hhh', t, o + 6 + 6 * j) for j in range(count)]
            self.frames[fid] = (a, b, parts)

    def sprite(self, section):
        s = self.sections[section]
        offs = _offsets(s)
        return [Block(s[o:(offs[i + 1] if i + 1 < len(offs) else len(s))]) for i, o in enumerate(offs)]

    def frame_layers(self, fid, stp_alpha=255, pal=0):
        """The frame's parts, each an RGBA image on the same square centred on the sprite origin, first to
        last (the engine draws each part as its own primitive, the last on top: overlapping blended parts
        add up). STP colours get alpha `stp_alpha`; the palette is `pal` + the frame's word a rows below."""
        fr = self.frames.get(fid)
        if fr is None or not fr[2]:
            return []
        half = 1
        for rect, x, y in fr[2]:
            if rect < len(self.rects):
                _u, _v, w, h = self.rects[rect][:4]
                half = max(half, abs(x), abs(y), abs(x + w), abs(y + h))
        out = []
        for rect, x, y in fr[2]:
            if rect >= len(self.rects):
                continue
            u, v, w, h, clx, cly, _ = self.rects[rect]
            page = self.pages[min(u // 256, len(self.pages) - 1)]
            part = Image.fromarray(page.crop(u % 256, v, w, h, clx, clut_row(cly, pal + fr[0]), stp_alpha), 'RGBA')
            layer = Image.new('RGBA', (2 * half, 2 * half), (0, 0, 0, 0))
            layer.paste(part, (half + x, half + y))
            out.append(layer)
        return out

    def frame_image(self, fid, stp_alpha=255, pal=0):
        """RGBA image of a frame: its parts composed with straight alpha (frame_layers), or None."""
        layers = self.frame_layers(fid, stp_alpha, pal)
        if not layers:
            return None
        im = layers[0].copy()
        for layer in layers[1:]:
            im.alpha_composite(layer)
        return im

    def draw_frame(self, canvas, origin, fid, x, y, sx=4096, sy=4096, rot=0, pal=0):
        """Alpha-composite a frame onto the canvas with its origin at (origin + (x, y)), scaled about its
        origin by sx, sy (4096 = 1.0) and rotated by rot (4096 = a full turn, sense guessed)."""
        im = self.frame_image(fid, pal=pal)
        if im is None or sx == 0 or sy == 0:
            return
        w, h = im.size
        nw, nh = min(2048, max(1, w * abs(sx) // 4096)), min(2048, max(1, h * abs(sy) // 4096))
        if (nw, nh) != (w, h):
            im = im.resize((nw, nh), Image.NEAREST)
        if sx < 0:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if sy < 0:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
        if rot % 4096:
            im = im.rotate(-rot * 360.0 / 4096, Image.NEAREST, expand=True)
        layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        layer.paste(im, (origin[0] + x - im.width // 2, origin[1] + y - im.height // 2))
        canvas.alpha_composite(layer)


# ------------------------------------------------------------------ as a 3D effect

PIXEL = 40              # field units per sprite pixel: a picture's size where the fighters stand (see dw3-effects.md)
TIM_W = 64              # the atlas: 64 halfwords = 256 4-bit texels wide


def clut_row(row, offset):
    """The palette row a rect draws with: its own plus the block's and frame's offsets. Rows past the page's
    256 are VRAM this decoder does not have: those draw with the rect's own palette (no colour cycling)."""
    return row + offset if row + offset < 256 else row


def _s16(v):
    return v - 65536 if v >= 32768 else v


def blend_of(pack, fid):
    """The frame's semi-transparency (its word b): None = opaque, else the PlayStation rate 0..3."""
    b = _s16(pack.frames[fid][1])
    return None if b < 0 else b & 3


def _atlas(pack, keys):
    """(tim bytes, {(rect, palette row offset): (u, v, w, h, clut)}) of the rects, shelf-packed into one
    256-texel wide 4-bit page (at most 256 rows, palettes in its bottom rows), all halved until they fit."""
    pals = {}
    for r, off in keys:
        u, v, w, h, clx, cly, _ = pack.rects[r]
        pals.setdefault((u // 256, clx, clut_row(cly, off)), len(pals))
    pal_rows = (len(pals) + 3) // 4
    for reduce in (1, 2, 4, 8):
        place, x, y, shelf = {}, 0, 0, 0
        for key in sorted(keys, key=lambda k: (-pack.rects[k[0]][3], k)):
            w, h = pack.rects[key[0]][2:4]
            w, h = max(2, w // reduce), max(1, h // reduce)
            w += w & 1                       # whole bytes
            if x + w > 4 * TIM_W:
                x, y, shelf = 0, y + shelf, 0
            place[key] = (x, y, w, h)
            x, shelf = x + w, max(shelf, h)
        if y + shelf + pal_rows <= 256:
            break
    else:
        raise ValueError('sprite atlas: rects do not fit 256 x 256 even at 1/8')
    rows = y + shelf + pal_rows
    idx = np.zeros((rows, 4 * TIM_W), np.uint8)
    out = {}
    for (r, off), (x, y, w, h) in place.items():
        u, v, sw, sh, clx, cly, _ = pack.rects[r]
        page = pack.pages[min(u // 256, len(pack.pages) - 1)]
        src = page.idx[v:v + sh, u % 256:u % 256 + sw]
        ys = (np.arange(h) * sh // h).clip(0, sh - 1)
        xs = (np.arange(w) * sw // w).clip(0, sw - 1)
        idx[y:y + h, x:x + w] = src[ys][:, xs]
        n = pals[(u // 256, clx, clut_row(cly, off))]
        out[(r, off)] = (x, y, w, h, (rows - pal_rows + n // 4) << 6 | n % 4)
    data = np.frombuffer((idx[:, 0::2] | idx[:, 1::2] << 4).astype(np.uint8).tobytes(), '<u2')
    data = data.reshape(rows, TIM_W).copy()
    for (pg, clx, cly), n in pals.items():
        page = pack.pages[min(pg, len(pack.pages) - 1)]
        data[rows - pal_rows + n // 4, 16 * (n % 4):16 * (n % 4) + 16] = page.hw[cly, clx:clx + 16]
    tim = struct.pack('<2I', 0x10, 2) + struct.pack('<I4H', 12 + data.nbytes, 0, 0, TIM_W, rows) + data.tobytes()
    return tim, out


def effect(disc, tables, sprite_id, pixel=PIXEL):
    """The sprite as a dw2effect.Effect in its own frame, one frame per 1/30 s: every (block, frame id,
    palette) a bone of flat quads, one per part, in the plane x = 0 (the picture's right is -z, toward the
    target; its down is +y), posed from the block's channels (position, scale, the turn in the picture's
    plane; turns about x and y only foreshorten, as the engine drops z) and hidden while another frame
    shows. Each frame's blend (its word b) goes on its quads."""
    from tools import dw2effect as D
    pack, blocks = sprite_blocks(disc, tables, sprite_id)
    step = TICKS // FPS
    used = {}
    for bi, b in enumerate(blocks):
        for k in range(0, b.count, step):
            st = b.at(k)
            fr = st and pack.frames.get(st['frame'])
            if fr and fr[2]:
                used.setdefault((bi, st['frame'], st['pal'] + fr[0]), None)
    keys = {(r, off) for (_bi, fid, off) in used for r, _x, _y in pack.frames[fid][2] if r < len(pack.rects)}
    if not keys:
        raise ValueError(f'sprite {sprite_id}: nothing drawn')
    tim, place = _atlas(pack, keys)
    bones, poses, bone_of = [], [], {}
    for (bi, fid, off) in used:
        verts, prims = [], []
        blend = blend_of(pack, fid)
        for r, x, y in reversed(pack.frames[fid][2]):        # the engine draws the last part on top
            if (r, off) not in place:
                continue
            u, v, w, h, clut = place[(r, off)]
            sw, sh = pack.rects[r][2], pack.rects[r][3]
            n = len(verts)
            for dy in (0, sh):
                for dx in (0, sw):
                    verts.append((0, (y + dy) * pixel, -(x + dx) * pixel))
            uvs = ((u, v), (u + w - 1, v), (u, v + h - 1), (u + w - 1, v + h - 1))
            prims.append(D.Prim((n, n + 1, n + 2, n + 3), uvs, clut, blend))
        bone_of[(bi, fid, off)] = len(bones)
        bones.append(D.Bone(-1, verts, prims))
        poses.append({0: ((0,) * 9, (0, 0, 0))})
    frames = []
    for k in range(0, max(b.count for b in blocks), step):
        row = [0] * len(bones)
        for bi, b in enumerate(blocks):
            st = b.at(k)
            fr = st and pack.frames.get(st['frame'])
            if not fr or (bi, st['frame'], st['pal'] + fr[0]) not in bone_of:
                continue
            j = bone_of[(bi, st['frame'], st['pal'] + fr[0])]
            a = st['rot'] * 2 * math.pi / 4096               # clockwise on screen
            c, s = math.cos(a), math.sin(a)
            sx, sy = b.flat_scale(st)
            m = ((1, 0, 0), (0, c * sy, -s * sx), (0, s * sy, c * sx))
            m9 = tuple(max(-32768, min(32767, int(round(m[r][q] * 4096)))) for r in range(3) for q in range(3))
            pose = (m9, (0, st['y'] * pixel, -st['x'] * pixel))
            ks = poses[j]
            idx = next((i for i, p in ks.items() if p == pose), None)
            if idx is None:
                idx = len(ks)
                ks[idx] = pose
            row[j] = idx
        frames.append(row)
    return D.Effect(bones, tim, poses, frames)


# ------------------------------------------------------------------ disc tables

def pack_records(disc, tables):
    """The fight overlay's 16-byte sprite pack records, as u16 words, by pack index."""
    fight = disc.read('FIGHTSTG.PRO')
    packs = max(tables.sprite_files) + 1
    for start in range(0, len(fight) - 16 * packs, 2):
        f = struct.unpack_from('<H', fight, start + 6)[0]
        if disc.name_of(f) == 'E000COM1.BIN' and disc.name_of(
                struct.unpack_from('<H', fight, start + 22)[0]) == 'E000COM2.BIN':
            return [struct.unpack_from('<8H', fight, start + 16 * k) for k in range(packs)]
    raise SystemExit('dw3sprite: no sprite pack table')


def _pack(disc, tables, p):
    """Pack p of `tables`, read once per disc: cached on the disc object by file and sections, since pack
    indices differ between tables (dw3effect.EffectIds numbers only one technique's packs) and an id() of a
    freed disc can return for another."""
    cache = disc.__dict__.setdefault('_sprite_packs', {})
    name = tables.sprite_files[p]
    if hasattr(tables, 'pack_sections'):          # dw3effect.EffectIds: no fight overlay to read
        tex, table = tables.pack_sections[p]
    else:
        if 'records' not in cache:
            cache['records'] = pack_records(disc, tables)
        rec = cache['records'][p]
        tex, table = rec[0], rec[2]
    com = 'F' + name[1:] if name.startswith('E000COM') else None
    key = (name, tex, table)
    if key not in cache:
        cache[key] = Pack(disc, name, tex, table, com)
    return cache[key]


def sprite_blocks(disc, tables, sprite_id):
    p, section = tables.sprites[sprite_id]
    pack = _pack(disc, tables, p)
    return pack, pack.sprite(section)


def render(disc, tables, sprite_id, canvas=(640, 480), origin=(320, 240)):
    """The sprite as a list of RGBA PIL frames at 30 fps: every block drawn each tick (a block that has
    ended is hidden), the sprite origin at `origin` on a `canvas` sized image, then all frames cropped
    to the union of what was drawn (the same box for every frame, at least 32 x 32)."""
    pack, blocks = sprite_blocks(disc, tables, sprite_id)
    frames = []
    for t in range(0, max(b.count for b in blocks), TICKS // FPS):
        im = Image.new('RGBA', canvas, (0, 0, 0, 0))
        for b in blocks:
            st = b.at(t)
            if st is not None:
                fx, fy = b.flat_scale(st)
                pack.draw_frame(im, origin, st['frame'], st['x'], st['y'], int(fx * 4096), int(fy * 4096) or 1,
                                st['rot'], st['pal'])
        frames.append(im)
    box = None
    for im in frames:
        bb = im.getbbox()
        if bb:
            box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]),
                                          max(box[2], bb[2]), max(box[3], bb[3]))
    if box is None:
        return frames
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    hw, hh = max(16, (box[2] - box[0]) // 2 + 4), max(16, (box[3] - box[1]) // 2 + 4)
    return [im.crop((cx - hw, cy - hh, cx + hw, cy + hh)) for im in frames]


def contact_sheet(frames, cols=None, cell=None, bg=(70, 70, 80, 255)):
    cell = cell or frames[0].size
    cols = cols or max(1, min(12, 1900 // cell[0]))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * cell[0], rows * cell[1]), bg)
    for i, f in enumerate(frames):
        sheet.alpha_composite(f.resize(cell, Image.NEAREST) if f.size != cell else f,
                              (i % cols * cell[0], i // cols * cell[1]))
    return sheet


def main(argv=None):
    ap = argparse.ArgumentParser(description='render sprite effects to contact sheets')
    ap.add_argument('--disc')
    ap.add_argument('--out', required=True)
    ap.add_argument('ids', nargs='+', type=int)
    a = ap.parse_args(argv)
    from tools import dw3effect as X
    disc = X._disc(a)
    tables = X.Tables(disc)
    os.makedirs(a.out, exist_ok=True)
    for sid in a.ids:
        frames = render(disc, tables, sid)
        name = tables.sprite_files[tables.sprites[sid][0]][:-4]
        step = max(1, len(frames) // 40)
        contact_sheet(frames[::step]).save(os.path.join(a.out, '%d-%s.png' % (sid, name)))
        print(sid, name, len(frames), 'ticks')


if __name__ == '__main__':
    main()
