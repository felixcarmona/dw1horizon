#!/usr/bin/env python3
"""Flat sprites: the picture a Digimon turns into while it is flattened in a fight.

While a fighter is flattened, `renderFlatDigimon` hides its model and draws one 16x16 frame of its own texture on a
standing quad, through CLUT row 15 of its slot: idle and idle 2 alternate, then attack (when it spits) and hurt (when it
is hit). The original partner textures keep those four frames at (224, 96), (240, 96), (224, 112) and (240, 112)
of their 256x128 texture: an LCD-style drawing of the standing Digimon in two colours, a dark outline (0x0421) and a white fill (0x7FFF).
A species whose texture has nothing there (no art, an empty row 15) is invisible while flat.

`stamp` gives a species' texture its frames at build time, from our own art and the player's own texture:
  art        the species' four-frame icon (`content/icons/<id>.txt`, idle, idle 2, attack, hurt: the order of the flat
             frames), else the icon of the species whose texture it reuses, else `portraits.py`'s render of its model;
             converted from alpha to a white silhouette, a dark outline and a few short interior marks (`mono`).
  placement  where the originals have the frames when no face samples those texels and no texture animation copies
             from or over them; else the first free 32x32 block of the texture; else free 15x15 cells (a frame shows
             15x15 texels; with fewer than four, poses share indices decoded through separate unused CLUT rows).
             Each cell keeps a one-texel margin from the model.
  no room    when the model fills its whole page (a few imports) or leaves room for fewer than four frames,
             `make_room` copies the UV islands over a 15x15 window, texel for texel, into free texels and moves their
             faces' UVs with them: the model looks the same and the window is the frames'. A texture where even that
             finds no room stops the build (NoRoom).
  CLUT       row 15, which every imported model but two leaves free (the batch import merges palettes down to 15):
             the two colours. When the faces use row 15 too, the model's own row with a transparent entry and the
             most contrast draws the frames with its darkest and lightest colours (`shared_row`).
  kept       trusted native partner textures keep their own four frames. Borrowed native field-enemy pages use
             authored icons: monochrome noise in their corner can pass a palette-only check.
  trailer    after the TIM, inside the 0x4800 bytes the game reads: "FLT2", the (u, v) of the four frames and the
             four CLUT rows. The executable keeps them per model slot when it uploads the texture (patch
             Select-a-flat-palette-for-each-animation-frame); a texture without a trailer (the disc's own) uses the originals' frames.
A texture with fewer than 16 CLUT rows or smaller than 256x128 is completed with zeros.

Standard library only (the player's build runs it).

  flatsprite.py sheet OUT.png DIGI_DIR [ID ...]   the flat frames of a built disc folder (DIGI.DAT, CHDAT/ALLTIM.TIM)
"""
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

NATIVE = ((224, 96), (240, 96), (224, 112), (240, 112))   # idle, idle 2, attack, hurt (renderFlatDigimon)
CELL = 15                    # the texels a frame shows (setUVWH(..., 0xF, 0xF))
ROW = 15                     # the flat frames' CLUT row (clutPage + 0x3C0)
MAGIC = b'FLT2'
OUTLINE, FILL = 0x0421, 0x7FFF      # the originals' two colours
TEX_SIZE = 0x4800
W, H = 256, 128
# Shared-cell groups when fewer than four cells fit; their CLUT rows retain separate poses.
FRAME_FALLBACK = {1: (0, 0, 0, 0), 2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}


class NoRoom(Exception):
    pass


# ---------------------------------------------------------------- art
def mono(icon):
    """Draw LCD frames from alpha, independent of the body's colour or shading.

    Fit the whole animation in the 15x15 area actually sampled by the game. The
    silhouette gets a white body and an inward, four-connected one-pixel outline.
    Only short, high-contrast dark marks surrounded by body survive inside it;
    a small ink budget prevents armour, fur and shaded panels becoming noise.
    """
    import portraits
    pal = struct.unpack_from('<16H', icon, 0)
    luma = [(.299 * (c & 31) + .587 * (c >> 5 & 31) + .114 * (c >> 10 & 31)) * 8 for c in pal]
    frames = []
    for f in range(4):
        ox, oy = (f & 1) * 16, (f >> 1) * 16
        frames.append([[((icon[32 + (oy + y) * 16 + (ox + x) // 2] >> (4 * (x & 1))) & 15)
                        for x in range(16)] for y in range(16)])
    points = [(x, y) for fr in frames for y in range(16) for x in range(16) if pal[fr[y][x]]]
    if not points:
        return portraits._pack([0, OUTLINE, FILL] + [0] * 13, [[[0] * 16 for _ in range(16)]] * 4)
    x0, y0 = min(x for x, y in points), min(y for x, y in points)
    width, height = max(x for x, y in points) - x0 + 1, max(y for x, y in points) - y0 + 1
    scale = min(1, CELL / width, CELL / height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    left, top = (CELL - w) // 2, CELL - h
    out = []
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1))
    for fr in frames:
        source = {(left + x, top + y): fr[y0 + min(height - 1, int((y + .5) * height / h))]
                                               [x0 + min(width - 1, int((x + .5) * width / w))]
                  for y in range(h) for x in range(w)}
        body = {p for p, c in source.items() if pal[c]}
        edge = {p for p in body if any((p[0] + dx, p[1] + dy) not in body for dx, dy in steps)}
        interior = body - edge
        # Local contrast, rather than a palette threshold: dark body colours and
        # smooth shading are white too. Thin lines need bright body on both sides.
        candidates = {}
        for x, y in interior:
            value = luma[source[x, y]]
            contrast = max([0] + [min(luma[source[x - dx, y - dy]], luma[source[x + dx, y + dy]]) - value
                                  for dx, dy in ((1, 0), (0, 1), (2, 0), (0, 2))
                                  if (x - dx, y - dy) in body and (x + dx, y + dy) in body])
            if value < 100 and contrast >= 80:
                candidates[x, y] = contrast
        # Keep complete short marks, never a scattering of pixels from a large
        # internal mesh. Prefer the face (upper half) when several marks compete.
        groups = []
        remaining = set(candidates)
        while remaining:
            seed = min(remaining)
            group, todo = {seed}, [seed]
            remaining.remove(seed)
            while todo:
                x, y = todo.pop()
                for dx, dy in steps:
                    p = x + dx, y + dy
                    if p in remaining:
                        remaining.remove(p)
                        group.add(p)
                        todo.append(p)
            if len(group) <= 8:
                score = sum(candidates[p] for p in group) / len(group) + 40 * (1 - min(y for x, y in group) / CELL)
                groups.append((score, sorted(group)))
        ink, budget = set(), max(4, len(interior) // 8)
        for _, group in sorted(groups, reverse=True):
            if len(ink) + len(group) <= budget:
                ink.update(group)
        grid = [[0] * 16 for _ in range(16)]
        for x, y in body:
            grid[y][x] = 1 if (x, y) in edge or (x, y) in ink else 2
        out.append(grid)
    # Static source art still needs readable movement. Leave the sampling margin
    # empty and translate within it; authored animation otherwise stays intact.
    for f, (dx, dy) in enumerate(((0, 0), (0, -1), (1, -1), (-1, 0))):
        if f and out[f] == out[0]:
            points = [(x, y) for y in range(CELL) for x in range(CELL) if out[f][y][x]]
            if all(0 <= x + dx < CELL and 0 <= y + dy < CELL for x, y in points):
                out[f] = portraits._shift(out[f], dx, dy)
            else:
                # Full-size stills have no translation margin. Squash vertically
                # for the bob, lean forward for attack, recoil for hurt.
                tw, th, tx, ty = {1: (15, 14, 0, 0), 2: (14, 15, 1, 0), 3: (14, 13, 0, 2)}[f]
                grid = [[0] * 16 for _ in range(16)]
                for y in range(th):
                    for x in range(tw):
                        grid[ty + y][tx + x] = out[f][y * (CELL - 1) // (th - 1)][x * (CELL - 1) // (tw - 1)]
                out[f] = grid
    return portraits._pack([0, OUTLINE, FILL] + [0] * 13, out)


def merge_palette(model, nbones, rows, idx):
    """Free a redundant model palette by reindexing a face's colours exactly.

    Preserve every sampled texel and its margin, including faces on other rows
    that share those coordinates. Animated texture copies are left alone.
    """
    import mmd
    from models.audit_textures import row_of
    anims = mmd.MMD.parse(model, nbones).anims
    if any(ins['op'] == 'tex' for a in (anims.anims if anims else []) if a for ins in a.instrs):
        raise NoRoom('texture copies prevent palette compaction')
    used, faces = {}, []
    for off, p in prims_at(model):
        if not p.mode & 4:
            continue
        d = p.decode()
        row = row_of(d['cba'])
        faces.append((off, row, d['cba']))
        pixels = used.setdefault(row, set())
        for x, y in texels(d['uv']):
            pixels.update(Y * W + X for Y in range(max(0, y - 1), min(H, y + 2))
                          for X in range(max(0, x - 1), min(W, x + 2)))
    for source in sorted(used):
        for target in sorted(used):
            if source == target:
                continue
            remap = {}
            for p in used[source]:
                colour = rows[source][idx[p]]
                choices = [i for i, c in enumerate(rows[target]) if c == colour and all(
                    rows[r][i] == rows[r][idx[p]] for r in used if r != source and p in used[r])]
                if not choices:
                    break
                remap[p] = choices[0]
            else:
                out, pixels = bytearray(model), bytearray(idx)
                for p, i in remap.items():
                    pixels[p] = i
                for off, row, cba in faces:
                    if row == source:
                        struct.pack_into('<H', out, off + 6, cba + ((target - source) << 6))
                return bytes(out), pixels
    raise NoRoom('no model palette can be freed without changing sampled colours')


def palette_frames(icon, cells, rows, idx, face_rows):
    """Keep poses in shared cells through unused CLUT rows, without extra VRAM.

    A pair of two-colour frames has nine possible pixel combinations: store the
    combination as an index and let each pose's CLUT decode its own colour. Four
    poses in one cell need up to 81 combinations; retain the 16 most common,
    matching rare combinations with alpha weighted above interior ink.
    """
    from collections import Counter
    groups = {}
    for f, cell in enumerate(cells):
        groups.setdefault(cell, []).append(f)
    count = max(map(len, groups.values()))
    free = [r for r in range(15, -1, -1) if r not in face_rows]
    if len(free) < count:
        raise NoRoom(f'{count} shared poses need unused CLUT rows, only {len(free)} available')
    palettes = free[:count]
    pal = struct.unpack_from('<16H', icon)
    frames = []
    for f in range(4):
        ox, oy = (f & 1) * 16, (f >> 1) * 16
        frames.append([0 if pal[c] == 0 else 1 if pal[c] == OUTLINE else 2
                       for y in range(CELL) for x in range(CELL)
                       for c in [(icon[32 + (oy + y) * 16 + (ox + x) // 2] >> (4 * (x & 1))) & 15]])
    frame_rows = [0] * 4
    for (u, v), fs in groups.items():
        vectors = [tuple(frames[f][p] for f in fs) + (0,) * (count - len(fs)) for p in range(CELL * CELL)]
        zero = (0,) * count
        if count <= 2:
            codes = [(a, b)[:count] for b in range(3 if count == 2 else 1) for a in range(3)]
        else:
            frequency = Counter(vectors)
            codes = [zero] + sorted((v for v in frequency if v != zero), key=lambda v: (-frequency[v], v))[:15]
        # All groups use the same positional decoding when count <= 2. A four-
        # pose group is the sole cell, so its own codebook can occupy these rows.
        for j, row in enumerate(palettes):
            rows[row] = [(0, OUTLINE, FILL)[code[j]] for code in codes] + [0] * (16 - len(codes))
        lookup = {}
        for vector in set(vectors):
            lookup[vector] = min(range(len(codes)), key=lambda k: sum(
                0 if a == b else 4 if a == 0 or b == 0 else 1 for a, b in zip(vector, codes[k])))
        for p, vector in enumerate(vectors):
            idx[(v + p // CELL) * W + u + p % CELL] = lookup[vector]
        for j, f in enumerate(fs):
            frame_rows[f] = palettes[j]
    return frame_rows


FLAT_ICON_ALIASES = {102: 67}  # SandYanmamon shares Yanmamon's silhouette.


def art(s):
    """(icon bytes, where from) of a species definition: its drawing, the drawing of the species its texture comes from,
    else the render of its model (portraits.py), else the portraits' fallback icon."""
    import portraits
    for t, why in ((s['id'], 'icon'), ((s.get('texture') or {}).get('from'), 'icon of the texture\'s species'),
                   (FLAT_ICON_ALIASES.get(s['id']), 'icon of the same silhouette')):
        if t is not None:
            text = portraits.drawn_text(t)
            if text is not None:
                return portraits.drawn_icon(text), f'{why} {t}'
    try:
        return portraits.species_icon(s), 'model render'
    except Exception as ex:                  # (portraits.species_icons does the same) a model that cannot be rendered
        return portraits.fallback_icon(), f'fallback icon ({ex})'


# ---------------------------------------------------------------- texture
def parse_tim(blob):
    """(clut words [rows][16], cx, cy, pixel indices bytearray W*H, px, py, end offset) of a 4 bpp model TIM, padded
    to 16 rows and 256x128."""
    magic, flag = struct.unpack_from('<II', blob, 0)
    if magic != 0x10 or flag != 8:
        raise ValueError('expected a 4 bpp TIM with a CLUT')
    clen, cx, cy, cw, ch = struct.unpack_from('<IHHHH', blob, 8)
    rows = [list(struct.unpack_from(f'<{cw}H', blob, 20 + 2 * cw * r))[:16] + [0] * max(0, 16 - cw) for r in range(ch)]
    rows += [[0] * 16 for _ in range(16 - len(rows))]
    po = 8 + clen
    plen, px, py, pw, ph = struct.unpack_from('<IHHHH', blob, po)
    idx = bytearray(W * H)
    for y in range(min(ph, H)):
        line = blob[po + 12 + y * pw * 2:po + 12 + (y + 1) * pw * 2]
        for i, b in enumerate(line[:W // 2]):
            idx[y * W + 2 * i] = b & 15
            idx[y * W + 2 * i + 1] = b >> 4
    return rows[:16], cx, cy, idx, px, py, po + plen


def build_tim(rows, cx, cy, idx, px, py):
    clut = b''.join(struct.pack('<16H', *r) for r in rows)
    pix = bytes(idx[i] | idx[i + 1] << 4 for i in range(0, W * H, 2))
    return (struct.pack('<II', 0x10, 8) + struct.pack('<IHHHH', 12 + len(clut), cx, cy, 16, 16) + clut
            + struct.pack('<IHHHH', 12 + len(pix), px, py, W // 4, H) + pix)


def trailer(blob):
    """(four (u, v), CLUT row) of a texture's trailer, or None (the originals' frames)."""
    try:
        end = parse_tim(blob)[6]
    except (ValueError, struct.error):
        return None
    if blob[end:end + 4] != MAGIC:
        return None
    b = blob[end + 4:end + 13]
    return tuple((b[2 * i], b[2 * i + 1]) for i in range(4)), b[8]


def frame_rows(tex):
    """CLUT row for each pose (four rows fit the existing three-word slot record)."""
    if trailer(tex):
        end = parse_tim(tex)[6]
        return tuple(tex[end + 12:end + 16])
    return (ROW,) * 4


# ---------------------------------------------------------------- what the model uses
class Use:
    """The texels of the 256x128 texture a model needs: what its textured faces sample and what its texture animations
    copy from or over (`margin`: also every texel that near one). `free(x, y, w, h)` in constant time (a summed-area
    table)."""

    def __init__(self, marks, margin=1):
        grid = bytearray(W * H)
        for x, y in marks:
            for yy in range(max(0, y - margin), min(H, y + margin + 1)):
                for xx in range(max(0, x - margin), min(W, x + margin + 1)):
                    grid[yy * W + xx] = 1
        self.sat = sat = [0] * ((W + 1) * (H + 1))
        for y in range(H):
            run = 0
            for x in range(W):
                run += grid[y * W + x]
                sat[(y + 1) * (W + 1) + x + 1] = sat[y * (W + 1) + x + 1] + run

    def free(self, x, y, w, h):
        s, k = self.sat, W + 1
        return not (s[(y + h) * k + x + w] - s[y * k + x + w] - s[(y + h) * k + x] + s[y * k + x])


def texels(uv):
    """The texels (x, y) whose centres lie in a face's UV polygon (3 or 4 points in TMD order: a quad is the triangles
    0 1 2 and 1 3 2), as `models/audit_textures.texels` finds them, one span per row; a degenerate triangle gives its
    corners."""
    out = set()
    for a, b, c in [(uv[0], uv[1], uv[2])] + ([(uv[1], uv[3], uv[2])] if len(uv) == 4 else []):
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if area == 0:
            out.update(p for p in (a, b, c))
            continue
        s = 1 if area > 0 else -1
        for y in range(min(a[1], b[1], c[1]), max(a[1], b[1], c[1]) + 1):
            py, lo, hi = y + .5, -1e9, 1e9
            for p, q in ((a, b), (b, c), (c, a)):
                # s * ((q.x - p.x) * (py - p.y) - (q.y - p.y) * (px - p.x)) >= 0, linear in px
                k = -s * (q[1] - p[1])
                m = s * ((q[0] - p[0]) * (py - p[1]) + (q[1] - p[1]) * p[0])
                if k > 0:
                    lo = max(lo, -m / k)
                elif k < 0:
                    hi = min(hi, -m / k)
                elif m < 0:
                    lo, hi = 1, 0
            x0 = max(min(a[0], b[0], c[0]), math.ceil(lo - .5))
            x1 = min(max(a[0], b[0], c[0]), math.floor(hi - .5))
            out.update((x, y) for x in range(x0, x1 + 1))
    if not out:
        out = {tuple(p) for p in uv}
    return out


def model_use(models, nbones):
    """((Use with a one-texel margin, Use without), set of the CLUT rows the textured faces use) of a model (MMD bytes)
    or of every model in a list that draws with the same texture."""
    import mmd
    from models.audit_textures import row_of
    marks, rows = set(), set()
    for model in ([models] if isinstance(models, (bytes, bytearray)) else models):
        tmd = mmd.TMD.parse(model, struct.unpack_from('<I', model, 0)[0])
        for ob in tmd.objects:
            for p in ob.prims:
                if p.mode & 4:
                    d = p.decode()
                    rows.add(row_of(d['cba']))
                    marks.update(texels(d['uv']))
        anims = mmd.MMD.parse(model, nbones).anims
        for a in (anims.anims if anims else []):
            for ins in (a.instrs if a else []):
                if ins['op'] == 'tex':
                    (w, h) = ins['size']
                    for sx, sy in (ins['src'], ins['dst']):
                        marks.update((sx * 4 + x, sy + y) for y in range(h) for x in range(w * 4))
    marks = [(x, y) for x, y in marks if 0 <= x < W and 0 <= y < H]
    return (Use(marks), Use(marks, 0)), rows


def place(uses, keep=()):
    """The four (u, v) of the flat frames in a texture whose model needs `uses` (with a margin, without): the
    originals' corner, else a free 31x31 block, else free 15x15 cells (a frame shows 15x15 texels, CELL), each with a
    texel of margin from what the model uses. Fewer than four cells share indices (FRAME_FALLBACK), decoded by palette_frames; NoRoom with none."""
    use = uses[0]
    if use.free(224, 96, 32, 32):
        return NATIVE
    for y in range(H - 32, -1, -1):          # nearest the originals' corner first: bottom rows, right columns
        for x in range(W - 32, -1, -1):
            if use.free(x, y, 31, 31):
                return ((x, y), (x + 16, y), (x, y + 16), (x + 16, y + 16))
    # setUVWH stores the far endpoint in a byte too; do not wrap 255 + 1.
    cells = [p for p in dict.fromkeys(keep) if p[0] + CELL < W and p[1] + CELL < H and use.free(*p, CELL, CELL)]
    for y in range(H - CELL - 1, -1, -1):
        for x in range(W - CELL - 1, -1, -1):
            if len(cells) < 4 and use.free(x, y, CELL, CELL) and not any(
                    abs(x - cx) < CELL and abs(y - cy) < CELL for cx, cy in cells):
                cells.append((x, y))
    if not cells:
        raise NoRoom('no free 15x15 texels for the flat sprite')
    return tuple(cells[k] for k in FRAME_FALLBACK[len(cells)])


def _luma(c):
    return .299 * ((c & 31) << 3) + .587 * ((c >> 5 & 31) << 3) + .114 * ((c >> 10 & 31) << 3)


def shared_row(clut):
    """(row, transparent index, dark index, light index) of the model's own CLUT row that best draws a two-colour
    sprite: one with a transparent entry (0x0000), the most contrast between its darkest and lightest colours."""
    best = None
    for r, pal in enumerate(clut):
        if 0 not in pal:
            continue
        cols = [(i, c) for i, c in enumerate(pal) if c]
        if len(cols) < 2:
            continue
        dark = min(cols, key=lambda ic: (_luma(ic[1]), ic[0]))
        light = max(cols, key=lambda ic: (_luma(ic[1]), -ic[0]))
        score = _luma(light[1]) - _luma(dark[1])
        if best is None or score > best[0]:
            best = (score, (r, pal.index(0), dark[0], light[0]))
    if best is None:
        raise NoRoom('CLUT row 15 is used by the model and no other row has a transparent colour')
    return best[1]


def native_sprite_ok(rows, idx, uses, face_rows):
    """The texture already has the four frames where the originals keep them (its own drawing: a native texture, a
    two-colour hand-made baby): row 15 is the sprite's alone, no face samples the corner, every frame has an opaque texel."""
    if ROW in face_rows or not any(rows[ROW]) or not uses[1].free(224, 96, 32, 32):
        return False
    colours = {rows[ROW][idx[(v + y) * W + u + x]] for u, v in NATIVE for y in range(16) for x in range(16)}
    opaque = colours - {0}
    # Native pages also use STP black (0x8000) and STP white (0xFFFF).
    monochrome = len(opaque) <= 2 and all(
        max(c & 31, c >> 5 & 31, c >> 10 & 31) - min(c & 31, c >> 5 & 31, c >> 10 & 31) <= 1 for c in opaque)
    return monochrome and all(
        any(rows[ROW][idx[(v + y) * W + u + x]] for y in range(CELL) for x in range(CELL)) for u, v in NATIVE)


# ---------------------------------------------------------------- making room
def prims_at(model):
    """[(offset in the model, Prim)] of every primitive, in TMD order."""
    import mmd
    base = struct.unpack_from('<I', model, 0)[0]
    nobj = struct.unpack_from('<I', model, base + 8)[0]
    o0, out = base + 12, []
    for i in range(nobj):
        pt, np_ = struct.unpack_from('<II', model, o0 + 28 * i + 16)
        p = o0 + pt
        for _ in range(np_):
            ln = 4 + model[p + 1] * 4
            out.append((p, mmd.Prim(model[p:p + ln])))
            p += ln
    return out


def make_room(model, nbones, idx, keep=(), _reuse_sources=True):
    """(model, texel indices) with one 15x15 window of the texture freed for the frames, when the model's faces fill the
    whole page: the UV islands (faces that share texels) over the cheapest window and its one-texel border are copied,
    texel for texel and with a texel of margin, into free texels elsewhere and their faces' UVs moved with them;
    nothing is scaled or redrawn.
    Windows that a texture animation copies from or over, or whose islands it touches, windows already free and windows
    near the cells in `keep` (frames already placed) are not used. NoRoom when no window can be freed."""
    import mmd
    faces = []                                    # (prim offset, uv, texels)
    for off, p in prims_at(model):
        if p.mode & 4 and p.mode >> 5 == 1:
            uv = p.decode()['uv']
            ts = texels(uv)
            if any((b[0] - a[0]) * (c[1] - a[1]) == (b[1] - a[1]) * (c[0] - a[0])
                   for a, b, c in [uv[:3]] + ([(uv[1], uv[3], uv[2])] if len(uv) == 4 else [])):
                # a flat (zero-area) UV triangle: the GPU still reads along its edges, the whole box goes with it
                ts |= {(x, y) for x in range(min(u for u, _ in uv), max(u for u, _ in uv) + 1)
                       for y in range(min(v for _, v in uv), max(v for _, v in uv) + 1)}
            faces.append((off, uv, {(x, y) for x, y in ts if 0 <= x < W and 0 <= y < H}))
    anim = set()
    anims = mmd.MMD.parse(model, nbones).anims
    for a in (anims.anims if anims else []):
        for ins in (a.instrs if a else []):
            if ins['op'] == 'tex':
                (w, h) = ins['size']
                for sx, sy in (ins['src'], ins['dst']):
                    anim.update((sx * 4 + x, sy + y) for y in range(h) for x in range(w * 4))
    # islands: faces that share a texel (union-find)
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for i, (_, _, ts) in enumerate(faces):
        for t in ts:
            if t in owner:
                parent[find(i)] = find(owner[t])
            else:
                owner[t] = i
    islands = {}
    for i in range(len(faces)):
        islands.setdefault(find(i), []).append(i)
    texels_of = {k: set().union(*(faces[i][2] for i in v)) for k, v in islands.items()}
    grid = {}
    for k, ts in texels_of.items():
        for t in ts:
            grid.setdefault(t, set()).add(k)
    bad = {k for k, ts in texels_of.items() if ts & anim}
    used = set(grid) | anim
    full = (1 << W) - 1
    cands = []
    for y in range(0, H - CELL + 1, 2):
        for x in range(0, W - CELL + 1, 2):
            ks = set().union(*(grid[(xx, yy)] for yy in range(y - 1, y + CELL + 1)
                               for xx in range(x - 1, x + CELL + 1) if (xx, yy) in grid))
            if not ks or any(abs(x - kx) <= CELL and abs(y - ky) <= CELL for kx, ky in keep) or ks & bad or any((xx, yy) in anim for yy in range(y, y + CELL) for xx in range(x, x + CELL)):
                continue
            cands.append((sum(len(texels_of[k]) for k in ks), y, x, sorted(ks)))
    cands.sort()
    fixed_cache, shape_cache = {}, {}
    masks = {}
    for k, ts in texels_of.items():
        rows = [0] * H
        for x, y in ts:
            for yy in range(max(0, y - 1), min(H, y + 2)):
                rows[yy] |= 7 << x >> 1 if x else 3
        masks[k] = rows
    base = [0] * H
    for x, y in anim:
        for yy in range(max(0, y - 1), min(H, y + 2)):
            base[yy] |= 7 << x >> 1 if x else 3
    for kx, ky in keep:
        lo, hi = max(0, kx - 1), min(W, kx + CELL + 1)
        for y in range(max(0, ky - 1), min(H, ky + CELL + 1)):
            base[y] |= ((1 << (hi - lo)) - 1) << lo
    for _, wy, wx, ks in cands[:400]:
        win = [((full >> (W - CELL - 2)) << wx >> 1) if wy - 1 <= y < wy + CELL + 1 else 0 for y in range(H)]
        # Source texels of moved faces become free. Copy from the unchanged
        # input buffer, keeping every other face, animation and frame reserved.
        key = tuple(ks)
        if key not in fixed_cache:
            fixed = base[:]
            for k, rows in masks.items():
                if not _reuse_sources or k not in ks:
                    for y in range(H):
                        fixed[y] |= rows[y]
            fixed_cache[key] = fixed
        taken = [a | b for a, b in zip(fixed_cache[key], win)]
        moves = {}
        for k in ks:
            if k not in shape_cache:
                ts = texels_of[k]
                dil = {(x + dx, y + dy) for x, y in ts for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       if 0 <= x + dx < W and 0 <= y + dy < H}
                x0, x1 = min(x for x, _ in dil), max(x for x, _ in dil)
                y0, y1 = min(y for _, y in dil), max(y for _, y in dil)
                rows = [0] * (y1 - y0 + 1)
                for x, y in dil:
                    rows[y - y0] |= 1 << (x - x0)
                shape_cache[k] = dil, x0, x1, y0, rows
            dil, x0, x1, y0, rows = shape_cache[k]
            spot = None
            for Y in range(H - len(rows), -1, -1):
                for X in range(W - (x1 - x0) - 1, -1, -1):
                    if all(not (taken[Y + r] >> X) & m for r, m in enumerate(rows)):
                        spot = (X, Y)
                        break
                if spot:
                    break
            if spot is None:
                break
            moves[k] = (spot[0] - x0, spot[1] - y0, dil)
            for r, m in enumerate(rows):
                taken[spot[1] + r] |= m << spot[0]
        if len(moves) != len(ks):
            continue
        out, new = bytearray(model), bytearray(idx)
        for k, (dx, dy, dil) in moves.items():
            for x, y in dil:
                new[(y + dy) * W + x + dx] = idx[y * W + x]
            for i in islands[k]:
                off, uv, _ = faces[i]
                for j, (u, v) in enumerate(uv):
                    out[off + 4 + 4 * j] = u + dx
                    out[off + 5 + 4 * j] = v + dy
        return bytes(out), new
    raise NoRoom('the model fills its texture and no 15x15 window can be freed')


def stamp(tex, model, nbones, icon, *, keep_native=True):
    """(texture bytes, model bytes, four (u, v), CLUT row, how). A texture that already has its frames
    (`native_sprite_ok`, when `keep_native` permits trusting the source) gets only its trailer; any other gets
    `icon` (0x220 bytes, already recoloured: `mono`) at
    `place`, in CLUT row 15, or, when the model's faces use row 15, in the row `shared_row` picks (its own colours). When
    the model leaves no room, `make_room` moves a few of its UV islands first (`model` changes only then; a list of
    models, all drawn with this texture, is never changed). NoRoom when even that fails."""
    rows, cx, cy, idx, px, py, _ = parse_tim(tex)
    uses, face_rows = model_use(model, nbones)
    free_rows = len(set(range(16)) - face_rows)
    if keep_native and native_sprite_ok(rows, idx, uses, face_rows):
        cells, row, how = NATIVE, ROW, 'its own'
        pose_rows = [row] * 4
    else:
        how = ''
        try:
            cells = place(uses)
        except NoRoom:
            if not isinstance(model, (bytes, bytearray)):
                raise
            model, idx = make_room(model, nbones, idx, _reuse_sources=free_rows > 1)
            cells, how = place(model_use(model, nbones)[0]), ', UV islands moved'
        while (len(set(cells)) < 2 or max(cells.count(c) for c in cells) > free_rows) and isinstance(model, (bytes, bytearray)):
            # Prefer two cells (lossless paired encoding); make more when the
            # model leaves too few palette rows for shared poses.
            try:
                m2, i2 = make_room(model, nbones, idx, set(cells), _reuse_sources=free_rows > 1)
            except NoRoom:
                break
            c2 = place(model_use(m2, nbones)[0], cells)
            if len(set(c2)) <= len(set(cells)):
                break
            model, idx, cells, how = m2, i2, c2, ', UV islands moved'
        if len(set(cells)) < 4:
            while max(cells.count(c) for c in cells) > len(set(range(16)) - face_rows):
                if not isinstance(model, (bytes, bytearray)):
                    raise NoRoom('shared textures leave too few unused palettes for the poses')
                model, idx = merge_palette(model, nbones, rows, idx)
                uses, face_rows = model_use(model, nbones)
                how += ', model palette merged'
            pose_rows = palette_frames(icon, cells, rows, idx, face_rows)
            row = pose_rows[0]
            how = 'palette poses' + how + ', moved'
        else:
            row, clear, dark, light = (ROW, 0, 0, 0) if ROW not in face_rows else shared_row(rows)
            pal = struct.unpack_from('<16H', icon, 0)
            if row == ROW:
                remap, how = list(range(16)), 'row 15' + how
                rows[ROW] = list(pal)
            else:
                remap = [clear if c == 0 else dark if c == OUTLINE else light for c in pal]
                how = f'row {row} shared' + how
            pix = icon[32:]
            n = 16 if cells == NATIVE else CELL
            for f, (u, v) in enumerate(cells):
                ox, oy = (f & 1) * 16, (f >> 1) * 16
                for y in range(n):
                    for x in range(n):
                        b = pix[(oy + y) * 16 + (ox + x) // 2]
                        idx[(v + y) * W + u + x] = remap[b >> 4 if (ox + x) & 1 else b & 15]
            how += '' if cells == NATIVE else ', moved'
            pose_rows = [row] * 4
    out = build_tim(rows, cx, cy, idx, px, py) + MAGIC + bytes(c for uv in cells for c in uv) + bytes(pose_rows)
    if len(out) > TEX_SIZE:
        raise ValueError('the texture does not fit 0x4800 bytes')
    return (out + tex[len(out):]).ljust(TEX_SIZE, b'\0')[:TEX_SIZE], model, cells, row, how


def sprite_of(tex):
    """(four (u, v), CLUT row) a texture's flat frames use: its trailer's, else the originals'."""
    t = trailer(tex)
    return t if t else (NATIVE, ROW)


def frames_of(tex):
    """[4 x 16x16 rows of colour words] of a texture's flat frames (the game shows 15x15 of each)."""
    rows, _, _, idx, _, _, _ = parse_tim(tex)
    cells, row = sprite_of(tex)
    pose_rows = frame_rows(tex)
    return [[[rows[pose_rows[f]][idx[(v + y) * W + u + x]] if u + x < W and v + y < H else 0 for x in range(16)]
             for y in range(16)] for f, (u, v) in enumerate(cells)]


def matches_art(tex, icon):
    """Whether all visible frame silhouettes match the supplied two-colour art.

    A monochrome palette alone cannot distinguish authored frames from texture noise.
    Palette colours may be shared with a model; compare transparency, not colour words.
    """
    actual = frames_of(tex)
    pal = struct.unpack_from('<16H', icon, 0)
    for f in range(4):
        ox, oy = (f & 1) * 16, (f >> 1) * 16
        for y in range(CELL):
            for x in range(CELL):
                b = icon[32 + (oy + y) * 16 + (ox + x) // 2]
                colour = pal[(b >> 4 if (ox + x) & 1 else b) & 15]
                if bool(actual[f][y][x]) != bool(colour):
                    return False
    return True


def check(tex, model=None, nbones=None):
    """Problems of a texture's flat sprite (empty list: fine): empty CLUT row or frame, more than two opaque colours;
    with the model (MMD bytes, or a list drawn with this texture): frames on texels the model uses, or row 15 holding
    the sprite while faces use it."""
    out = []
    try:
        rows = parse_tim(tex)[0]
    except (ValueError, struct.error) as e:
        return [f'unreadable texture: {e}']
    cells, row = sprite_of(tex)
    if not 0 <= row < 16 or not any(rows[row]):
        out.append(f'CLUT row {row} is empty')
    frames = frames_of(tex)
    colours = {c for fr in frames for line in fr[:CELL] for c in line[:CELL] if c}
    if len(colours) > 2:
        out.append(f'flat frames use {len(colours)} opaque colours (expected at most two)')
    for f, fr in enumerate(frames):
        u, v = cells[f]
        if u + CELL >= W or v + CELL >= H:
            out.append(f'frame {f} at {(u, v)} wraps its GPU UV endpoint or crosses the texture slot')
        if not any(c for r in fr[:CELL] for c in r[:CELL]):
            out.append(f'frame {f} at {cells[f]} has no opaque texel')
    if model is not None:
        uses, face_rows = model_use(model, nbones)
        for f, (u, v) in enumerate(cells):      # a moved frame keeps a texel of margin, the originals' corner none
            if not uses[cells == NATIVE].free(u, v, CELL, CELL):
                out.append(f'frame {f} at {(u, v)} lies on texels the model uses')
        overlap = set(frame_rows(tex)) & face_rows
        if overlap and (row == ROW or len(set(frame_rows(tex))) > 1):
            out.append(f'CLUT rows {sorted(overlap)} hold the sprite but faces use them too')
    return out


# ---------------------------------------------------------------- contact sheet
def sheet(out, disc, ids=None, zoom=4):
    """PNG of every species' four flat frames (from a built disc folder), 13 to a row, with the id and name under each."""
    import image
    from models.audit_textures import disc_models
    tiles = []
    for t, name, model, tim in disc_models(disc, set(ids or ())):
        tiles.append((t, name, frames_of(tim)))
    cols = 13
    cw, chh = max(32 * zoom + 8, 160), 32 * zoom + 32
    Wd, Hd = cols * cw, -(-len(tiles) // cols) * chh
    px = bytearray(b'\x18\x18\x18\xff' * (Wd * Hd))
    for k, (t, name, fr) in enumerate(tiles):
        ox, oy = (k % cols) * cw + 4, (k // cols) * chh + 4
        for f in range(4):
            for y in range(CELL):
                for x in range(CELL):
                    c = fr[f][y][x]
                    rgb = (((c & 31) << 3), ((c >> 5 & 31) << 3), ((c >> 10 & 31) << 3), 255) if c else (70, 70, 70, 255)
                    for zy in range(zoom):
                        for zx in range(zoom):
                            X = ox + ((f & 1) * 16 + x) * zoom + zx
                            Y = oy + ((f >> 1) * 16 + y) * zoom + zy
                            px[(Y * Wd + X) * 4:(Y * Wd + X) * 4 + 4] = bytes(rgb)
    im = image.frombytes('RGBA', (Wd, Hd), bytes(px))
    draw = image.ImageDraw.Draw(im)
    for k, (t, name, _) in enumerate(tiles):
        draw.text(((k % cols) * cw + 4, (k // cols) * chh + 32 * zoom + 7),
                  f'{t} {name}', fill=(240, 240, 240, 255))
    im.save(out)
    return [t for t, _, _ in tiles]


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('sheet')
    a.add_argument('out')
    a.add_argument('disc')
    a.add_argument('ids', nargs='*', type=int)
    a = ap.parse_args()
    if a.cmd == 'sheet':
        ids = sheet(a.out, a.disc, a.ids)
        print(f'{a.out}: {len(ids)} species')


if __name__ == '__main__':
    main()
