#!/usr/bin/env python3
"""Portraits of the imported species: a 32x32 icon of each model, in the format the game's menus use.

The originals' portraits are drawn by hand: STDDAT/STDTIM.BIN holds 32x32 tiles of four 16x16 frames
(idle, idle 2, attack, hurt) for the tournament bracket and the VS screens, and ETCDAT/SBOY.TIM holds
16x16 pairs (normal, highlighted) for the evolution chart. A species of DIGI.DAT has neither, so
`tools/species.py build` stores one icon per species (this module renders it) and the game loads it into
free VRAM when a screen shows the species.

Icon (ICON_SIZE = 0x220 bytes): 16 colours of a CLUT (0x20 bytes: index 0 transparent, 15 the outline)
and 32x32 pixels at 4 bpp (0x200 bytes, 16 bytes per row, low nibble first as in VRAM) in four 16x16 frames:
  (0,0) idle, (16,0) idle shifted one pixel up (the highlighted box of the chart, the second idle frame),
  (0,16) attack (leans forward), (16,16) hurt (flashed). The top 32x16 strip is the chart's pair.

The icon is the front view of the species' rest pose (animation slot 0, first tick) with its texture,
rendered at 4x, box-filtered to the 14x14 inside a one-pixel outline, quantized to 14 colours.

Usage (from the repository root):
  portraits.py sheet OUT.png [ID|NAME ...]   contact sheet of the icons (all species of the content folders
                                             by default), 8x zoom, with the four frames of each
  portraits.py icon ID|NAME OUT.png          one icon, 16x zoom
  portraits.py fallback OUT.png              the icon of a species without one
  portraits.py ref TYPE OUT.png              an original's tile (STDTIM) and chart pair (SBOY) for comparison

Standard library only (tools/mmd.py, tools/animsheet.py), with tools/image.py for the PNGs of this CLI.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import hashlib
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

ICON_SIZE = 0x220            # CLUT 0x20 + 4bpp 32x32 0x200
ICONS_PER_SECTOR = 3         # DIGI.DAT packs them 3 to a 2048-byte sector
VERSION = 4                  # renderer version: part of the cache key
CACHE = os.environ.get('DW_PORTRAITS_CACHE') or os.path.join(ROOT, 'build', 'portraits-cache')   # (a player's build: tools/derive's species step puts it in its output folder)
OUTLINE = (24, 20, 40)
SIZE = 112                   # render size: 8x the 14x14 inside the outline
YAW, PITCH = 40.0, 8.0       # three-quarter view from the left, slightly from above (the originals' tiles face left)


# ---------------------------------------------------------------- rendering
def _render(m, tim, nb, skel, yaw=YAW, pitch=PITCH, size=SIZE):
    """RGBA bytes size x size (alpha 0 = background) of the rest pose, fitted to the box."""
    import animsheet
    import mmd
    frames, _, _ = animsheet.slot_frames(m, nb, 0, max_ticks=2)
    pose = frames[0]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    tris = animsheet.world_tris(m, pose, skel)
    cam = animsheet.Camera(yaw, pitch)
    pts = [cam.view(v) for t in tris for v in t[0]]
    mnx, mxx = min(p[0] for p in pts), max(p[0] for p in pts)
    mny, mxy = min(p[1] for p in pts), max(p[1] for p in pts)
    span = max(mxx - mnx, mxy - mny, 1)
    # the model fills the box (a 1/8 margin for the outline); aligned to the bottom centre
    sc = size * 0.875 / span
    ox = size / 2 - (mnx + mxx) / 2 * sc
    oy = size - size * 0.0625 - mxy * sc
    img = bytearray(size * size * 4)
    animsheet.raster(tris, cam, tim, size, sc, ox, oy, img, 0, size)
    return img


def _downsample(img, size=SIZE, out=14):
    """Box filter to out x out: (r, g, b) or None per pixel."""
    k = size // out if size % out == 0 else None
    f = size / out
    res = []
    for y in range(out):
        row = []
        for x in range(out):
            x0, x1 = int(x * f), max(int((x + 1) * f), int(x * f) + 1)
            y0, y1 = int(y * f), max(int((y + 1) * f), int(y * f) + 1)
            n = cov = 0
            r = g = b = 0
            for yy in range(y0, min(y1, size)):
                for xx in range(x0, min(x1, size)):
                    n += 1
                    i = 4 * (yy * size + xx)
                    if img[i + 3]:
                        cov += 1
                        r += img[i]; g += img[i + 1]; b += img[i + 2]
            row.append((r // cov, g // cov, b // cov) if cov * 5 >= n * 2 else None)   # 40 % covered: opaque
        res.append(row)
    return res


def _c15(rgb):
    r, g, b = rgb
    c = (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10
    return c or 0x8000


def _enhance(rgb):
    """The flat shading of the software renderer is dull next to hand-drawn sprites: more contrast and colour."""
    r, g, b = rgb
    m = (r + g + b) / 3
    out = []
    for v in (r, g, b):
        v = m + (v - m) * 1.25          # saturation
        v = (v - 110) * 1.15 + 128      # contrast and brightness
        out.append(max(0, min(255, int(v))))
    return tuple(out)


def _quantize(grid, n=14):
    import mmd
    cols = [_enhance(p) for row in grid for p in row if p is not None]
    if not cols:
        return [], None
    uniq = sorted(set(cols))
    pal = mmd.quantize(cols, n) if len(uniq) > n else uniq
    return pal, None


def _nearest(pal, p):
    return min(range(len(pal)), key=lambda i: sum((pal[i][k] - p[k]) ** 2 for k in range(3)))


def _frame_pixels(grid, pal):
    """16x16 palette indices (0 transparent, 1..14 colours, 15 outline) from the 14x14 grid, centred."""
    f = [[0] * 16 for _ in range(16)]
    for y in range(14):
        for x in range(14):
            p = grid[y][x]
            if p is not None:
                f[y + 1][x + 1] = 1 + _nearest(pal, _enhance(p))
    out = [row[:] for row in f]
    for y in range(16):
        for x in range(16):
            if f[y][x] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < 16 and 0 <= yy < 16 and f[yy][xx] != 0:
                        out[y][x] = 15
                        break
    return out


def _shift(f, dx, dy):
    out = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            yy, xx = y - dy, x - dx
            if 0 <= yy < 16 and 0 <= xx < 16:
                out[y][x] = f[yy][xx]
    return out


def make_icon(rgba=None, grid=None):
    """Icon bytes (ICON_SIZE) from a rendered RGBA image (or a 14x14 grid of (r, g, b) / None)."""
    if grid is None:
        grid = _downsample(rgba)
    pal, _ = _quantize(grid)
    if not pal:
        return fallback_icon()
    f0 = _frame_pixels(grid, pal)
    f1 = _shift(f0, 0, -1)
    f2 = _shift(f0, 1, 0)
    # hurt: the same sprite flashed (white tint) and sunk one pixel
    f3 = _shift(f0, 0, 1)
    colors = [0] + [_c15(c) for c in pal]
    colors += [0x8000] * (15 - len(colors))
    colors.append(_c15(OUTLINE))
    return _pack(colors, [f0, f1, f2, f3], hurt=3)


def _pack(colors, frames, hurt=None):
    """CLUT + 32x32 4bpp. A CLUT has one palette, so the flash of the `hurt` frame is made by remapping its
    indices to the nearest brighter entry of the same palette."""
    img = [[0] * 32 for _ in range(32)]
    for fi, f in enumerate(frames):
        ox, oy = (fi & 1) * 16, (fi >> 1) * 16
        for y in range(16):
            for x in range(16):
                v = f[y][x]
                if hurt is not None and fi == hurt and 1 <= v <= 14:
                    v = _brighter(colors, v)
                img[oy + y][ox + x] = v
    clut = struct.pack('<16H', *colors)
    pix = bytearray()
    for row in img:
        for x in range(0, 32, 2):
            pix.append(row[x] | row[x + 1] << 4)
    return clut + bytes(pix)


def _brighter(colors, i):
    """The palette entry closest to a brighter version of colour i (itself when none is)."""
    def rgb(c):
        return ((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3)
    r, g, b = rgb(colors[i])
    t = (min(255, r + 70), min(255, g + 70), min(255, b + 70))
    best, bd = i, 1 << 30
    for j in range(1, 15):
        cr, cg, cb = rgb(colors[j])
        d = (cr - t[0]) ** 2 + (cg - t[1]) ** 2 + (cb - t[2]) ** 2
        if d < bd:
            best, bd = j, d
    return best


# a hand-made '?' egg for a species without a model
_FALLBACK = [
    '................',
    '.....oooooo.....',
    '....oWWWWWWo....',
    '...oWWWKKWWWo...',
    '..oWWWKwwKWWWo..',
    '..oWWWKwwKWWWo..',
    '..oWWWWWKWWWWo..',
    '..oWWWWKWWWWWo..',
    '..oWWWWKWWWWWo..',
    '..oWWWWWWWWWWo..',
    '..oWWWWKWWWWWo..',
    '..oWWWWKWWWWWo..',
    '...oWWWWWWWWo...',
    '....oWWWWWWo....',
    '.....oooooo.....',
    '................',
]


def fallback_icon():
    pal = {'W': (200, 200, 216), 'K': (88, 88, 136), 'w': (240, 240, 250)}
    cols = [0, _c15(pal['W']), _c15(pal['K']), _c15(pal['w'])] + [0x8000] * 11 + [_c15(OUTLINE)]
    cols = cols[:15] + [_c15(OUTLINE)]
    idx = {'.': 0, 'W': 1, 'K': 2, 'w': 3, 'o': 15}
    f0 = [[idx[c] for c in row] for row in _FALLBACK]
    return _pack(cols, [f0, _shift(f0, 0, -1), _shift(f0, 1, 0), _shift(f0, 0, 1)])


# ---------------------------------------------------------------- species
def species_icon(s, use_cache=True, yaw=None, pitch=None):
    """The icon of a species definition (content JSON dict with '_path'). Cached by the model's and the
    texture's bytes."""
    import species
    import mmd
    model, mpath = species.species_model(s)
    tex = species.species_texture(s)
    yaw = YAW if yaw is None else yaw
    pitch = PITCH if pitch is None else pitch
    key = hashlib.sha1(model + tex + f'{VERSION}/{yaw}/{pitch}/{s["id"]}'.encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, f'{s["id"]}-{key}.bin')
    if use_cache and os.path.exists(cp):
        return open(cp, 'rb').read()
    r = species.species_record(s)
    t = s['id']
    e = mmd.exe()
    e.add_type(t, r['bones'], name=s['name'])
    m = mmd.MMD.load(mpath, t)
    nb, skel = e.bone_count[t], e.skeleton[t]
    img = _render(m, mmd.Tim4(tex), nb, skel, yaw, pitch)
    icon = make_icon(img)
    os.makedirs(CACHE, exist_ok=True)
    open(cp, 'wb').write(icon)
    return icon


def species_icons(content=None, only=None, progress=False, yaw=None, pitch=None):
    """{id: icon bytes} of every species of the content folders (species.py CONTENT by default)."""
    import species
    content = content or species.CONTENT
    out = {}
    for t, s in sorted(species.imports(content).items()):
        if only and t not in only:
            continue
        try:
            out[t] = species_icon(s, yaw=yaw, pitch=pitch)
        except Exception as ex:                      # a species that cannot be rendered gets the fallback
            print(f'portraits: {s.get("name")} ({t}): {ex}: fallback icon', file=sys.stderr)
            out[t] = fallback_icon()
        if progress:
            print(f'  {t} {s["name"]}', flush=True)
    return out


# ---------------------------------------------------------------- png output
def icon_rgba(icon, frame=None):
    """RGBA of the whole 32x32 tile (frame None) or one 16x16 frame."""
    pal = struct.unpack_from('<16H', icon, 0)
    px = icon[0x20:]
    rows = []
    for y in range(32):
        row = []
        for x in range(32):
            b = px[y * 16 + x // 2]
            v = b >> 4 if x & 1 else b & 15
            c = pal[v]
            if v == 0:
                row.append((0, 0, 0, 0))
            else:
                row.append(((c & 31) << 3 | (c & 31) >> 2, (c >> 5 & 31) << 3 | (c >> 5 & 31) >> 2,
                            (c >> 10 & 31) << 3 | (c >> 10 & 31) >> 2, 255))
        rows.append(row)
    if frame is not None:
        ox, oy = (frame & 1) * 16, (frame >> 1) * 16
        rows = [r[ox:ox + 16] for r in rows[oy:oy + 16]]
    return rows


def sheet(icons, names, out, zoom=6, cols=8):
    from tools.image import Image
    n = len(icons)
    rows = -(-n // cols)
    cell = 32 * zoom + 8
    im = Image.new('RGBA', (cols * cell, rows * cell + 0), (70, 74, 90, 255))
    for i, (t, icon) in enumerate(icons):
        tile = Image.new('RGBA', (32, 32))
        tile.putdata([p for r in icon_rgba(icon) for p in r])
        tile = tile.resize((32 * zoom, 32 * zoom), Image.NEAREST)
        x, y = (i % cols) * cell + 4, (i // cols) * cell + 4
        im.paste(tile, (x, y), tile)
    im.save(out)


def _ref(t, out):
    """An original's STDTIM tile and SBOY chart pair next to each other."""
    from tools.image import Image
    sys.path.insert(0, HERE)
    import mmd  # noqa: F401
    ex = os.path.join(ROOT, 'extracted')
    d = open(os.path.join(ex, 'STDDAT', 'STDTIM.BIN'), 'rb').read()
    sl = (t - 1) % 64
    off = 0 if (t - 1) // 64 == 0 else 0x8220
    _, _, cl, (x, y, w, h), pix = _tim(d, off)
    im = Image.new('RGBA', (32, 32))
    px = []
    for yy in range(32):
        for xx in range(32):
            ux, uy = (sl % 8) * 32 + xx, (sl // 8) * 32 + yy
            b = pix[uy * 128 + ux // 2]
            v = b >> 4 if ux & 1 else b & 15
            c = cl[v]
            px.append((0, 0, 0, 0) if v == 0 else ((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3, 255))
    im.putdata(px)
    im.resize((256, 256), Image.NEAREST).save(out)


def _tim(d, off):
    fl = struct.unpack_from('<I', d, off + 4)[0]
    o = off + 8
    bl = struct.unpack_from('<I', d, o)[0]
    cx, cy, cw, ch = struct.unpack_from('<4H', d, o + 4)
    cl = struct.unpack_from('<%dH' % (cw * ch), d, o + 12)
    o += bl
    bl2 = struct.unpack_from('<I', d, o)[0]
    x, y, w, h = struct.unpack_from('<4H', d, o + 4)
    return fl, (cx, cy, cw, ch), cl, (x, y, w, h), d[o + 12:o + 8 + bl2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet'); p.add_argument('out'); p.add_argument('ids', nargs='*')
    p.add_argument('--content'); p.add_argument('--zoom', type=int, default=6); p.add_argument('--cols', type=int, default=8)
    p.add_argument('--yaw', type=float); p.add_argument('--pitch', type=float)
    p = sub.add_parser('icon'); p.add_argument('id'); p.add_argument('out'); p.add_argument('--content')
    p = sub.add_parser('fallback'); p.add_argument('out')
    p = sub.add_parser('ref'); p.add_argument('type', type=int); p.add_argument('out')
    a = ap.parse_args()
    import species
    if a.cmd == 'fallback':
        sheet([(0, fallback_icon())], [''], a.out, zoom=16, cols=1)
        return
    if a.cmd == 'ref':
        _ref(a.type, a.out)
        return
    content = a.content or species.CONTENT
    allsp = species.imports(content)

    def pick(x):
        for t, s in allsp.items():
            if str(t) == x or s['name'].lower() == x.lower():
                return t
        raise SystemExit(f'no species {x}')
    if a.cmd == 'icon':
        t = pick(a.id)
        sheet([(t, species_icon(allsp[t]))], [allsp[t]['name']], a.out, zoom=16, cols=1)
    else:
        only = {pick(x) for x in a.ids} if a.ids else None
        icons = species_icons(content, only, progress=True, yaw=a.yaw, pitch=a.pitch)
        sheet(sorted(icons.items()), None, a.out, zoom=a.zoom, cols=a.cols)
        print(f'{a.out}: {len(icons)} icons')


if __name__ == '__main__':
    main()
