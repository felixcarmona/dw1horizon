#!/usr/bin/env python3
"""Flat sprites: the picture a Digimon turns into while it is flattened in a fight.

While a fighter is flattened, `renderFlatDigimon` hides its model and draws one 16x16 frame of its own texture on a
standing quad, through CLUT row 15 of its slot: idle and idle 2 alternate, then attack (when it spits) and hurt (when it
is hit). Every original keeps those four frames at (224, 96), (240, 96), (224, 112) and (240, 112) of its 256x128
texture: an LCD-style drawing of the standing Digimon in two colours, a dark outline (0x0421) and a white fill (0x7FFF).
A species whose texture has nothing there (no art, an empty row 15) is invisible while flat.

`stamp` gives a species' texture its frames at build time, from our own art and the player's own texture:
  art        the species' four-frame icon (`content/icons/<id>.txt`, idle, idle 2, attack, hurt: the order of the flat
             frames), else the icon of the species whose texture it reuses, else `portraits.py`'s render of its model;
             recoloured as the originals' frames are: colours darker than LUMA_OUTLINE become the outline, the rest
             the fill (`mono`).
  placement  where the originals have the frames when no face samples those texels and no texture animation copies
             from or over them; else the first free 32x32 block of the texture; else free 15x15 cells (a frame shows
             15x15 texels; with fewer than four, frames share a cell: FRAME_FALLBACK); the one-texel margin around
             the model's texels is dropped only when it leaves fewer than four cells.
  no room    when the model fills its whole page (a few imports) or leaves room for fewer than four frames,
             `make_room` copies the UV islands over a 15x15 window, texel for texel, into free texels and moves their
             faces' UVs with them: the model looks the same and the window is the frames'. A texture where even that
             finds no room stops the build (NoRoom).
  CLUT       row 15, which every imported model but two leaves free (the batch import merges palettes down to 15):
             the two colours. When the faces use row 15 too, the model's own row with a transparent entry and the
             most contrast draws the frames with its darkest and lightest colours (`shared_row`).
  kept       a texture that already has its four frames there (a native texture, a hand-made baby's drawing) keeps them.
  trailer    after the TIM, inside the 0x4800 bytes the game reads: "FLT1", the (u, v) of the four frames and the
             CLUT row. The executable keeps them per model slot when it uploads the texture (patch
             Flat-sprites-...); a texture without a trailer (the disc's own) uses the originals' frames.
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
MAGIC = b'FLT1'
OUTLINE, FILL = 0x0421, 0x7FFF      # the originals' two colours
LUMA_OUTLINE = 70            # icon colours darker than this (0..255 luma) become the outline: the originals draw a
                             # white body with black lines; at 110 dark-coloured Digimon turned into black blobs
TEX_SIZE = 0x4800
W, H = 256, 128
# frames that share a cell when the texture has fewer than four free cells: idle and attack first, then idle 2, hurt
FRAME_FALLBACK = {1: (0, 0, 0, 0), 2: (0, 1, 0, 1), 3: (0, 1, 2, 1), 4: (0, 1, 2, 3)}


class NoRoom(Exception):
    pass


# ---------------------------------------------------------------- art
def mono(icon):
    """The icon (portraits.ICON_SIZE bytes: CLUT + 32x32 4 bpp) with its colours turned into the originals' two."""
    pal = struct.unpack_from('<16H', icon, 0)
    out = []
    for c in pal:
        if c == 0:
            out.append(0)
            continue
        r, g, b = (c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3
        out.append(OUTLINE if .299 * r + .587 * g + .114 * b < LUMA_OUTLINE else FILL)
    return struct.pack('<16H', *out) + icon[32:]


def art(s):
    """(icon bytes, where from) of a species definition: its drawing, the drawing of the species its texture comes from,
    else the render of its model (portraits.py), else the portraits' fallback icon."""
    import portraits
    for t, why in ((s['id'], 'icon'), ((s.get('texture') or {}).get('from'), 'icon of the texture\'s species')):
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


def place(uses):
    """The four (u, v) of the flat frames in a texture whose model needs `uses` (with a margin, without): the
    originals' corner, else a free 31x31 block, else free 15x15 cells (a frame shows 15x15 texels, CELL), each with a
    texel of margin from what the model uses. Fewer than four cells repeat frames (FRAME_FALLBACK); NoRoom with none."""
    use = uses[0]
    if use.free(224, 96, 32, 32):
        return NATIVE
    for y in range(H - 31, -1, -1):          # nearest the originals' corner first: bottom rows, right columns
        for x in range(W - 31, -1, -1):
            if use.free(x, y, 31, 31):
                return ((x, y), (x + 16, y), (x, y + 16), (x + 16, y + 16))
    cells = []
    for y in range(H - CELL, -1, -1):
        for x in range(W - CELL, -1, -1):
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
    hand-made baby): row 15 is the sprite's alone, no face samples the corner, every frame has an opaque texel."""
    if ROW in face_rows or not any(rows[ROW]) or not uses[1].free(224, 96, 32, 32):
        return False
    return all(any(rows[ROW][idx[(v + y) * W + u + x]] for y in range(16) for x in range(16)) for u, v in NATIVE)


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


def make_room(model, nbones, idx, keep=()):
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
    grid = {t: find(i) for t, i in owner.items()}
    bad = {k for k, ts in texels_of.items() if ts & anim}
    used = set(grid) | anim
    occ = [0] * H
    for x, y in used:
        for yy in range(max(0, y - 1), min(H, y + 2)):
            occ[yy] |= 7 << x >> 1 if x else 3
    full = (1 << W) - 1
    cands = []
    for y in range(0, H - CELL + 1, 2):
        for x in range(0, W - CELL + 1, 2):
            ks = {grid[(xx, yy)] for yy in range(y - 1, y + CELL + 1) for xx in range(x - 1, x + CELL + 1) if (xx, yy) in grid}
            if not ks or any(abs(x - kx) <= CELL and abs(y - ky) <= CELL for kx, ky in keep) or ks & bad or any((xx, yy) in anim for yy in range(y, y + CELL) for xx in range(x, x + CELL)):
                continue
            cands.append((sum(len(texels_of[k]) for k in ks), y, x, sorted(ks)))
    cands.sort()
    for _, wy, wx, ks in cands[:400]:
        win = [((full >> (W - CELL - 2)) << wx >> 1) if wy - 1 <= y < wy + CELL + 1 else 0 for y in range(H)]
        taken = [occ[y] | win[y] for y in range(H)]
        moves = {}
        for k in ks:
            ts = texels_of[k]
            dil = {(x + dx, y + dy) for x, y in ts for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   if 0 <= x + dx < W and 0 <= y + dy < H}
            x0, y0 = min(x for x, _ in dil), min(y for _, y in dil)
            x1, y1 = max(x for x, _ in dil), max(y for _, y in dil)
            rows = [0] * (y1 - y0 + 1)
            for x, y in dil:
                rows[y - y0] |= 1 << (x - x0)
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


def stamp(tex, model, nbones, icon):
    """(texture bytes, model bytes, four (u, v), CLUT row, how). A texture that already has its frames
    (`native_sprite_ok`) gets only its trailer; any other gets `icon` (0x220 bytes, already recoloured: `mono`) at
    `place`, in CLUT row 15, or, when the model's faces use row 15, in the row `shared_row` picks (its own colours). When
    the model leaves no room, `make_room` moves a few of its UV islands first (`model` changes only then; a list of
    models, all drawn with this texture, is never changed). NoRoom when even that fails."""
    rows, cx, cy, idx, px, py, _ = parse_tim(tex)
    uses, face_rows = model_use(model, nbones)
    if native_sprite_ok(rows, idx, uses, face_rows):
        cells, row, how = NATIVE, ROW, 'its own'
    else:
        how = ''
        try:
            cells = place(uses)
        except NoRoom:
            if not isinstance(model, (bytes, bytearray)):
                raise
            model, idx = make_room(model, nbones, idx)
            cells, how = place(model_use(model, nbones)[0]), ', UV islands moved'
        while len(set(cells)) < 4 and isinstance(model, (bytes, bytearray)):   # frames sharing a cell: room for more
            try:
                m2, i2 = make_room(model, nbones, idx, set(cells))
            except NoRoom:
                break
            c2 = place(model_use(m2, nbones)[0])
            if len(set(c2)) <= len(set(cells)):
                break
            model, idx, cells, how = m2, i2, c2, ', UV islands moved'
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
    out = build_tim(rows, cx, cy, idx, px, py) + MAGIC + bytes(c for uv in cells for c in uv) + bytes((row, 0, 0, 0))
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
    return [[[rows[row][idx[(v + y) * W + u + x]] if u + x < W and v + y < H else 0 for x in range(16)]
             for y in range(16)] for u, v in cells]


def check(tex, model=None, nbones=None):
    """Problems of a texture's flat sprite (empty list: fine): its CLUT row empty, a frame with no opaque texel, and with
    the model (MMD bytes, or a list drawn with this texture): a frame on texels the model uses, row 15 holding the
    sprite while faces use it."""
    out = []
    try:
        rows = parse_tim(tex)[0]
    except (ValueError, struct.error) as e:
        return [f'unreadable texture: {e}']
    cells, row = sprite_of(tex)
    if not 0 <= row < 16 or not any(rows[row]):
        out.append(f'CLUT row {row} is empty')
    for f, fr in enumerate(frames_of(tex)):
        if not any(c for r in fr[:CELL] for c in r[:CELL]):
            out.append(f'frame {f} at {cells[f]} has no opaque texel')
    if model is not None:
        uses, face_rows = model_use(model, nbones)
        for f, (u, v) in enumerate(cells):      # a moved frame keeps a texel of margin, the originals' corner none
            if not uses[cells == NATIVE].free(u, v, CELL, CELL):
                out.append(f'frame {f} at {(u, v)} lies on texels the model uses')
        if row == ROW and ROW in face_rows:
            out.append(f'CLUT row {ROW} holds the sprite but faces use it too')
    return out


# ---------------------------------------------------------------- contact sheet
def sheet(out, disc, ids=None, zoom=4):
    """PNG of every species' four flat frames (from a built disc folder), eight to a row, with the id under each."""
    import image
    from models.audit_textures import disc_models
    tiles = []
    for t, name, model, tim in disc_models(disc, set(ids or ())):
        tiles.append((t, name, frames_of(tim)))
    cols = 8
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
