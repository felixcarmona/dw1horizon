#!/usr/bin/env python3
"""Digimon World 2 (PS1, USA) Digimon models -> Digimon World MMDs.

DW2 draws its Digimon with DW1's own meshes at x5.1 (rigid one-mesh-per-bone, Y down,
4 bpp texture, per-face palettes), but its texture is a 128x256 page with the palettes
stored as rows of the image, and its animations are per-frame key matrices. The data is
read with the `dw2` package of $DW2_ROOT (docs/dw1-port.md there); the
DW1 side is tools/mmdport.py, shared with tools/dcb2mmd.py and tools/dw3mmd.py.
Documented in docs/mods/models.md, "Importing from Digimon World 2".

  dw2mmd.py info CODE                        bones, budgets, texture layout, palettes, animations
                                             (CODE = the model file, e.g. M237CHMR)
  dw2mmd.py convert CODE TYPE OUT_DIR [--height H | --scale S] [--slot A0=0,0x21 ...]
  dw2mmd.py partner SPEC.json OUT_DIR        a full partner (mmdport.build_partner + blinks)
  dw2mmd.py sheet CODE OUT.png [--every 6]   the source animations through the converted model
  dw2mmd.py batch [NAME ...]                 every DW2-source Digimon of
                                             docs/data/crossgame-sources.csv -> imported/<Name>/mmd/,
                                             budgets, round trip, a contact sheet against DW2's render

What the conversion does:
- scale: DW2 = DW1 x 5.1; the factor is measured per model against the Card Battle or DW1
  mesh of the same Digimon when crossgame.py pairs them (identical/modified), else 1/5.1;
  `--height` / `--scale` override it;
- bones: DW2 bone i (depth-first, parent before child) -> DW1 bone i+1 with TMD object i,
  bone 0 = the entity; the rest pose is the first frame of the first animation (A0);
- faces: DW2 quads (0,1,2)+(1,3,2) and triangles are already TMD primitives (textured,
  Gouraud, one normal per corner); the "semi-transparency on" section becomes the
  semi-transparent modes (0x3E/0x36);
- texture (`repack`): the page is cut into its two 128x128 halves, side by side (rows
  128..255 move to u + 128, v - 128). Faces whose texels cross row 128 cannot be cut:
  each connected group of them (UV islands, palette ignored) is copied whole into texels
  no other face uses (FFT search for a free spot), and its UVs are moved. If that does not
  fit, every island is packed again from scratch. The texels a face covers are found
  exactly (triangle/texel-square overlap), so the copies are minimal;
- palettes: DW2 palettes are rows of the image (clut = row << 6 | x / 16); identical ones
  are shared, and while more than 15 remain (row 15 is DW1's flat sprite) the cheapest pair
  is merged: texels only one palette reads are re-indexed to the merged palette's colours
  (exact while the union of colours fits 16), shared texels keep their index; every merge
  is logged with its colour error;
- blinks: DW2's texture-animation parts (texAnimParts after the bone tables: a destination,
  three source frames: open, half, closed) become DW1 texture-move instructions (code 3):
  open at frame 1 of every slot, a blink (half, closed, half, open: 0.2 s as in DW2) in the
  looping idle slots, closed eyes for the whole slot where DW2 closes them (hit B0,
  knock-backs C0-C2, lying K0);
- animations: each frame's key matrix is split into rotation x per-axis scale (scale 0
  hides a part), sent through a glTF as quaternions and solved into DW1's Rx.Ry.Rz by
  mmd.import_anims; DW2 plays one frame per two 60 Hz ticks (Anim_StepModelAnim), i.e.
  30 fps, resampled to DW1's 20 ticks/s; a looping animation gets its loop-start frame
  appended so the loop closes, and its speed is nudged (< 2 %) so the loop is a whole
  number of ticks.

Releases: the recipes are made from the USA disc. The disc read is $DW2_DISC (default
$DW2_ROOT/disc, the USA one); its boot file tells the release. DigimonWorld 2 (Japan) has every
file of the recipes' models as the USA disc does; tools/dw2release.py checks that as they are read.

The bundled player converter uses only the Python standard library.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import csv
import glob
import json
import math
import os
import struct
import sys
from collections import Counter

DW2_ROOT = os.environ.get('DW2_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2'))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def _dw2():
    if DW2_ROOT not in sys.path:
        sys.path.insert(0, DW2_ROOT)
    import dw2.model, dw2.texture, dw2.gltf  # noqa: E401
    return dw2


import mmd  # noqa: E402
import mmdport  # noqa: E402

FPS = 30.0                 # one DW2 frame per two 60 Hz ticks
DW2_SCALE = 5.1            # DW2 units / DW1 units (crossgame.py: 5.10-5.15 on the 110 shared meshes)
MAX_PALETTES = 15          # row 15 is the flat sprite's (renderFlatDigimon)
SLOT_W, SLOT_H = 256, 128
SOURCES_CSV = os.path.join(ROOT, 'docs', 'data', 'crossgame-sources.csv')
MODELS_CSV = os.path.join(ROOT, 'docs', 'data', 'crossgame-models.csv')
IMPORTED = os.path.join(ROOT, 'imported')

# DW2 battle animation kinds (crossgame.md, from ref/DW2-PC stag3000/fighter.c) and the
# default DW1 slots of `convert` (like dcb2mmd's DEFAULT_SLOTS)
KINDS = {'A0': 'idle', 'B0': 'hit', 'C0': 'knock-back', 'C1': 'knock-back', 'C2': 'knock-back',
         'D0': 'field idle', 'D1': 'walk', 'D2': 'field', 'D5': 'run', 'F0': 'technique 1',
         'G0': 'technique 2', 'H0': 'technique 3', 'I0': 'second action', 'J0': 'downed', 'K0': 'lying'}
DEFAULT_SLOTS = {'A0': [0x00, 0x21], 'D1': [0x02], 'D5': [0x03], 'B0': [0x28], 'C0': [0x29], 'J0': [0x2B],
                 'F0': [0x2E], 'G0': [0x2F], 'H0': [0x30], 'I0': [0x31]}
LOOPING = {'A0', 'D0', 'D1', 'D5'}       # played as infinite loops; the rest once
# Gfx_AnimAllowsBlink: animation ids 10 (B0), 20-22 (C0-C2) and 100 (K0) show closed eyes
CLOSED_EYES = {'B0', 'C0', 'C1', 'C2', 'K0'}
BLINK_SLOTS = (0x00, 0x01, 0x21, 0x22)  # looping idles that get a blink


# boot file -> release. The recipes are made from the USA disc; another release's disc is read only when every
# file of a recipe's model is the USA one (tools/dw2release.py).
RELEASES = {'SLUS_011.93': 'us', 'SLPS_028.44': 'jp'}


def disc_dir():
    return os.environ.get('DW2_DISC', os.path.join(DW2_ROOT, 'disc'))


def release():
    """The release of the disc in disc_dir(), told by its boot file."""
    cnf = open(os.path.join(disc_dir(), 'SYSTEM.CNF'), encoding='latin-1').read()
    boot = cnf.split('cdrom:')[1].lstrip('\\').split(';')[0].strip().upper()
    if boot not in RELEASES:
        raise SystemExit(f'dw2mmd: {disc_dir()} boots {boot}, not a known Digimon World 2 release')
    return RELEASES[boot]


def model_path(code):
    g = glob.glob(os.path.join(disc_dir(), 'AAA', '4.AAA', 'MODEL', 'MODEL*', code + '.BIN'))
    if not g:
        raise SystemExit(f'{code}: no such DW2 model file')
    rel = release()
    if rel != 'us':
        import dw2release
        dw2release.check_model(rel, disc_dir(), code)
    return g[0]


def num(x):
    return int(x, 0) if isinstance(x, str) else int(x)


# ---------------------------------------------------------------- texture animation parts
def tex_anim_parts(data, nbones):
    """texAnimParts (ref/DW2-PC anim.c Gfx_AnimateModelTex, 156C.h GfxTexAnimPart): up to 10
    parts of 10 bytes {dstX, dstY, w, h, uv[6]} (x and w in halfwords = 4 pixels, relative
    to the texture). Parts 0 and 1 are blinks (dstX 0xFF = none): uv pairs 0/1/2 are the
    open, half and closed frames. Parts 2.. (until 0xFF/0xFE) cycle their three frames every
    24 60 Hz ticks; after a 0xFE come period-driven parts (GfxModelTexAnim)."""
    off = 12 + 16 * nbones
    blinks, cycles, timed = [], [], 0
    for i in range(10):
        e = data[off + 10 * i:off + 10 * i + 10]
        if len(e) < 10:
            break
        if i < 2:
            if e[0] != 0xFF:
                blinks.append(dict(dst=(e[0], e[1]), size=(e[2], e[3]), src=[(e[4], e[5]), (e[6], e[7]), (e[8], e[9])]))
            continue
        if e[0] in (0xFF, 0xFE):
            if e[0] == 0xFE:
                q = off + 10 * i + 1
                while timed < 10 and data[q] != 0xFF:
                    timed += 1
                    q += 0x2A
            break
        cycles.append(dict(dst=(e[0], e[1]), size=(e[2], e[3]), src=[(e[4], e[5]), (e[6], e[7]), (e[8], e[9])]))
    return dict(blinks=blinks, cycles=cycles, timed=timed)


# ---------------------------------------------------------------- texel footprints
from tools.derive.texel import footprint


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def _islands(fps_, members):
    """Groups of faces (indices into fps_) whose footprints overlap: UV islands."""
    import numeric as np
    uf = _UF(len(members))
    owner = {}
    for k, i in enumerate(members):
        x0, y0, m = fps_[i]
        ys, xs = np.nonzero(m)
        for y, x in zip((ys + y0).tolist(), (xs + x0).tolist()):
            j = owner.setdefault((x, y), k)
            if j != k:
                uf.union(j, k)
    groups = {}
    for k, i in enumerate(members):
        groups.setdefault(uf.find(k), []).append(i)
    return list(groups.values())


def _union_mask(rects):
    """rects: [(x0, y0, mask)] -> (x0, y0, mask) of their union."""
    import numeric as np
    X0 = min(r[0] for r in rects); Y0 = min(r[1] for r in rects)
    X1 = max(r[0] + r[2].shape[1] for r in rects); Y1 = max(r[1] + r[2].shape[0] for r in rects)
    m = np.zeros((Y1 - Y0, X1 - X0), bool)
    for x0, y0, r in rects:
        m[y0 - Y0:y0 - Y0 + r.shape[0], x0 - X0:x0 - X0 + r.shape[1]] |= r
    return X0, Y0, m


from tools.derive.texel import place as _place, window_pair


def repack(prims, src_idx, parts, log=print):
    """Lays the 128x256 DW2 page into DW1's 256x128 slot.
    prims: [dict(uvs=[(u, v)], ...)] (source coordinates); src_idx: uint8[256, 128] palette indices.
    Two 128-row windows of the page (rows a..a+127 and b..b+127, normally 0 and 128, chosen so
    that the fewest texels' worth of faces fit neither) go side by side; each face takes the
    first window that holds all its texels. The faces left over are moved island by island
    into free texels. If that fails every island is packed again from scratch.
    Returns (idx uint8[128, 256], new uvs per prim, blink moves, info dict)."""
    import numeric as np
    nf = len(prims)
    fps_ = [footprint(p['uvs']) for p in prims]
    rects = []
    for bi, b in enumerate(parts['blinks']):
        w, h = 4 * b['size'][0], b['size'][1]
        for kind, (x, y) in [('dst', b['dst'])] + [(f'src{k}', s) for k, s in enumerate(b['src'])]:
            rects.append(dict(part=bi, kind=kind, x=4 * x, y=y, w=w, h=h))
    # the two windows
    A, Bw = window_pair([(y0, y0 + m.shape[0], m.sum()) for x0, y0, m in fps_] +
                        [(r['y'], r['y'] + r['h'], 10 ** 6) for r in rects])

    def win_of(y0, h):
        if A <= y0 and y0 + h <= A + 128:
            return 0
        if Bw <= y0 and y0 + h <= Bw + 128:
            return 1
        return None

    def win_off(w):
        return (0, -A) if w == 0 else (128, -Bw)

    crossing = [i for i, (x0, y0, m) in enumerate(fps_) if win_of(y0, m.shape[0]) is None]
    info = dict(crossing_faces=sum(1 for x0, y0, m in fps_ if y0 < 128 < y0 + m.shape[0]), windows=(A, Bw),
                left_over=len(crossing), mode='halves', moved_islands=0, blinks_dropped=0)

    def dst_inside(X0, Y0, M):
        return [r for r in rects if r['kind'] == 'dst' and X0 <= r['x'] and r['x'] + r['w'] <= X0 + M.shape[1]
                and Y0 <= r['y'] and r['y'] + r['h'] <= Y0 + M.shape[0]]

    def put(page, occ, M, X0, Y0, align):
        at = _place(occ, M, align)
        if at is None:
            return None
        nx, ny = at
        occ[ny:ny + M.shape[0], nx:nx + M.shape[1]] |= M
        sub = page[ny:ny + M.shape[0], nx:nx + M.shape[1]]
        sub[M] = src_idx[Y0:Y0 + M.shape[0], X0:X0 + M.shape[1]][M]
        return nx, ny

    def try_windows():
        occ = np.zeros((SLOT_H, SLOT_W), bool)
        page = np.zeros((SLOT_H, SLOT_W), np.uint8)
        page[:, :128] = src_idx[A:A + 128]
        page[:, 128:] = src_idx[Bw:Bw + 128]
        uvs = [list(p['uvs']) for p in prims]
        cs = set(crossing)
        for i, (x0, y0, m) in enumerate(fps_):
            if i in cs:
                continue
            dx, dy = win_off(win_of(y0, m.shape[0]))
            occ[y0 + dy:y0 + dy + m.shape[0], x0 + dx:x0 + dx + m.shape[1]] |= m
            uvs[i] = [(u + dx, v + dy) for u, v in prims[i]['uvs']]
        pos = {}
        for r in rects:
            w = win_of(r['y'], r['h'])
            if w is None:
                continue
            dx, dy = win_off(w)
            occ[r['y'] + dy:r['y'] + dy + r['h'], r['x'] + dx:r['x'] + dx + r['w']] = True
            pos[(r['part'], r['kind'])] = [(r['x'] + dx, r['y'] + dy)]
        moved = 0
        groups = sorted(_islands(fps_, crossing), key=lambda g: -_union_mask([fps_[i] for i in g])[2].sum())
        for grp in groups:
            X0, Y0, M = _union_mask([fps_[i] for i in grp])
            inside = dst_inside(X0, Y0, M)
            at = put(page, occ, M, X0, Y0, (4, X0) if inside else None)
            if at is None:
                return None
            nx, ny = at
            for i in grp:
                uvs[i] = [(u + nx - X0, v + ny - Y0) for u, v in prims[i]['uvs']]
            for r in inside:
                key = (r['part'], 'dst')
                pos[key] = (pos.get(key) or []) + [(r['x'] + nx - X0, r['y'] + ny - Y0)]
            moved += 1
        # blink frames in neither window: copied whole to a free spot on a halfword
        for r in rects:
            if r['kind'] == 'dst' or (r['part'], r['kind']) in pos:
                continue
            at = put(page, occ, np.ones((r['h'], r['w']), bool), r['x'], r['y'], (4, 0))
            if at is not None:
                pos[(r['part'], r['kind'])] = [at]
        return page, uvs, pos, moved

    res = try_windows()
    if res is not None:
        out, new_uvs, rect_pos, info['moved_islands'] = res
    else:
        # every island packed again from scratch (largest first); a blink destination joins
        # the island of the faces that show it, its frames are islands of their own
        info['mode'] = 'repacked'
        dsts = [r for r in rects if r['kind'] == 'dst']
        pseudo = fps_ + [(r['x'], r['y'], np.ones((r['h'], r['w']), bool)) for r in dsts]
        items = []
        for grp in _islands(pseudo, list(range(len(pseudo)))):
            X0, Y0, M = _union_mask([pseudo[i] for i in grp])
            faces = [i for i in grp if i < nf]
            ds = [dsts[i - nf] for i in grp if i >= nf]
            if (M.shape[0] > SLOT_H or M.shape[1] > SLOT_W) and not ds:
                items += [([i], fps_[i], []) for i in faces]
            else:
                items.append((faces, (X0, Y0, M), ds))
        srcs = [r for r in rects if r['kind'] != 'dst']
        items += [([], (r['x'], r['y'], np.ones((r['h'], r['w']), bool)), [r]) for r in srcs]
        items.sort(key=lambda it: -it[1][2].sum())
        occ = np.zeros((SLOT_H, SLOT_W), bool)
        out = np.zeros((SLOT_H, SLOT_W), np.uint8)
        new_uvs = [list(p['uvs']) for p in prims]
        rect_pos = {}
        for faces, (X0, Y0, M), rs in items:
            at = put(out, occ, M, X0, Y0, (4, X0) if rs else None)
            if at is None:
                raise SystemExit(f'texture does not fit the 256x128 slot even repacked ({len(items)} islands)')
            nx, ny = at
            for i in faces:
                new_uvs[i] = [(u + nx - X0, v + ny - Y0) for u, v in prims[i]['uvs']]
            for r in rs:
                rect_pos[(r['part'], r['kind'])] = [(r['x'] + nx - X0, r['y'] + ny - Y0)]
        info['moved_islands'] = len(items)
    # blinks that survive: every rectangle placed, x on a halfword
    moves = []
    for bi, b in enumerate(parts['blinks']):
        keys = [(bi, 'dst')] + [(bi, f'src{k}') for k in range(3)]
        if any(not rect_pos.get(k) for k in keys) or any(x % 4 for k in keys for x, _ in rect_pos[k]):
            info['blinks_dropped'] += 1
            log(f'  blink part {bi}: a rectangle could not be placed on a halfword: dropped')
            continue
        moves.append(dict(size=(b['size'][0], b['size'][1]), dst=[(x // 4, y) for x, y in rect_pos[(bi, 'dst')]],
                          src=[(rect_pos[(bi, f'src{k}')][0][0] // 4, rect_pos[(bi, f'src{k}')][0][1]) for k in range(3)]))
    info['used_texels'] = int(occ_count(new_uvs))
    return out, new_uvs, moves, info


def occ_count(uvs_list):
    import numeric as np
    occ = np.zeros((SLOT_H, SLOT_W), bool)
    for uvs in uvs_list:
        x0, y0, m = footprint(uvs)
        occ[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] |= m
    return occ.sum()


# ---------------------------------------------------------------- palettes
def _rgb(c):
    return ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)


def colour_dist2(a, b):
    """Squared distance of two 15-bit colours (+ the STP bit); transparency (0x0000) against
    a colour counts as the largest error."""
    if a == b:
        return 0
    if (a == 0) != (b == 0):
        return 3 * 255 ** 2
    d = sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b)))
    return d + (64 if (a ^ b) & 0x8000 else 0)


def merge_palettes(idx, uvs_list, prim_pal, pals, maxp, log=print):
    """Merges palettes until at most `maxp` remain. idx: uint8[128, 256] (re-indexed in place);
    prim_pal: palette id per face (changed in place); pals: {id: [16 colours]} (changed).
    A texel only one palette reads can take any index of the merged palette (colours are
    added to its free entries, or the closest one is used); a texel several palettes read
    keeps its index. Returns [(from, into, faces, mean error per texel 0..255)]."""
    import numeric as np
    pixels = bytearray(idx.tobytes())
    bits = [0] * len(pixels)
    width = idx.shape[1]
    for uvs, p in zip(uvs_list, prim_pal):
        x0, y0, m = footprint(uvs)
        flag = 1 << p
        for dy, row in enumerate(m):
            offset = (y0 + dy) * width + x0
            for dx, used in enumerate(row):
                if used:
                    bits[offset + dx] |= flag
    report = []
    # identical palettes first (free)
    alive = sorted(pals)

    def plan(A, B):
        """Cost and plan of merging A into B."""
        C = list(pals[B])
        # Match np.unique's ascending insertion order: min(locked, key=...)
        # below preserves the original set iteration order on distance ties.
        locked = set(sorted(used_indices[B]))
        err, n = 0, 0
        for i, count in enumerate(shared_counts[A]):
            if not count: continue
            if i not in locked:
                C[i] = pals[A][i]
                locked.add(i)
            else:
                err += count * colour_dist2(pals[A][i], C[i])
            n += count
        remap = {}
        for i, count in enumerate(exclusive_counts[A]):
            if not count: continue
            a = pals[A][i]
            j = next((j for j in ([i] + sorted(locked)) if j in locked and C[j] == a), None)
            if j is None:
                free = [j for j in range(16) if j not in locked]
                if free:
                    j = i if i in free else free[0]
                    C[j] = a
                    locked.add(j)
                else:
                    j = min(locked, key=lambda k: colour_dist2(a, C[k]))
                    err += count * colour_dist2(a, C[j])
            remap[i] = j
            n += count
        return err, n, C, remap

    while True:
        same = [(A, B) for A in alive for B in alive if A != B and pals[A] == pals[B]]
        if not same and len(alive) <= maxp:
            break
        # A candidate's shared/exclusive counts depend only on its source
        # palette, not on the destination. Group equal texels once per merge
        # instead of rescanning the page for every ordered palette pair.
        used_indices = {p: set() for p in alive}
        shared_counts = {p: [0] * 16 for p in alive}
        exclusive_counts = {p: [0] * 16 for p in alive}
        for (mask, index), count in Counter(zip(bits, pixels)).items():
            remaining = mask
            while remaining:
                flag = remaining & -remaining
                p = flag.bit_length() - 1
                used_indices[p].add(index)
                counts = exclusive_counts[p] if mask == flag else shared_counts[p]
                counts[index] += count
                remaining ^= flag
        best = None
        cands = same[:1] if same else [(A, B) for A in alive for B in alive if A != B]
        for A, B in cands:
            e, n, C, remap = plan(A, B)
            if best is None or e < best[0]:
                best = (e, n, A, B, C, remap)
        e, n, A, B, C, remap = best
        flag, into = 1 << A, 1 << B
        for pos, mask in enumerate(bits):
            if mask & flag:
                if mask == flag:
                    pixels[pos] = remap[pixels[pos]]
                bits[pos] = (mask & ~flag) | into
        pals[B] = C
        faces = sum(1 for p in prim_pal if p == A)
        for k, p in enumerate(prim_pal):
            if p == A:
                prim_pal[k] = B
        alive.remove(A)
        del pals[A]
        err = math.sqrt(e / max(n, 1) / 3)
        report.append((A, B, faces, round(err, 1)))
        if not same:
            log(f'  palette {A} ({faces} faces) merged into {B}: mean colour error {err:.1f}/255 per texel')
    idx[:] = np.frombuffer(pixels, dtype=np.uint8).reshape(idx.shape)
    return report


# ---------------------------------------------------------------- scale
def measured_scale(code, log=print):
    """1 / (DW2 size / DW1 size) of this model, measured by crossgame.compare against the Card
    Battle or DW1 model of the same Digimon (when the two meshes are identical or modified),
    else 1/5.1. Returns (scale, how)."""
    try:
        import pickle
        rows = list(csv.DictReader(open(MODELS_CSV)))
        row = next((r for r in rows if code in (r.get('dw2') or '')), None)
        cache = os.path.join(ROOT, 'build', 'crossgame', 'models.pkl')
        if row is None or not os.path.exists(cache):
            return 1 / DW2_SCALE, 'default 1/5.1'
        data = pickle.load(open(cache, 'rb'))
        mine = next(r for r in data['dw2'] if r['code'] == code)
        # the relation is stored in the other game's column: rel_dw2 when DW1 is the reference,
        # rel_dcb when DW2 is (a Digimon DW1 lacks)
        pairs = [('dw1', row.get('rel_dw2') or '')] if row.get('reference') == 'DW1' else [('dcb', row.get('rel_dcb') or '')]
        for g, rel in pairs:
            ref = (row.get(g) or '').split(';')[0].split(' ')[0].strip()
            if not ref or not (rel.startswith('identical') or rel.startswith('modified')):
                continue
            cand = [r for r in data[g] if str(r['code']).lstrip('0') == ref.lstrip('0')]
            if not cand:
                continue
            import crossgame  # developer-only cache comparison; the player has no cache
            cm = crossgame.compare(cand[0], mine)
            if cm['ratio'] and cm['cls'] in ('identical', 'modified'):
                return 1 / cm['ratio'], f'measured against {g.upper()} {ref} ({cm["cls"]}): x{cm["ratio"]:.3f}'
        return 1 / DW2_SCALE, 'default 1/5.1 (no DW1 or Card Battle mesh of it)'
    except Exception as ex:          # the cache is optional
        log(f'  scale: {ex}; using 1/5.1')
        return 1 / DW2_SCALE, 'default 1/5.1'


# ---------------------------------------------------------------- loading
def load(code, scale=None, height=None, maxp=MAX_PALETTES, log=print):
    """The DW2 model as an mmdport.Model (texture repacked, palettes merged, animations
    as 30 fps frames). Extra attributes: blinks (texture moves), info (dict)."""
    dw2 = _dw2()
    import numeric as np
    from dw2.texture import image_halfwords
    from dw2.gltf import decompose
    path = model_path(code)
    data = open(path, 'rb').read()
    m = dw2.model.load(path)
    B = len(m.bones)
    hw = image_halfwords(m.texture)
    H = hw.shape[0]
    src_idx = np.empty((H, hw.shape[1] * 4), np.uint8)
    for i in range(4):
        src_idx[:, i::4] = (hw >> (4 * i)) & 0xF
    if src_idx.shape != (256, 128):
        raise SystemExit(f'{code}: texture is {src_idx.shape[1]}x{src_idx.shape[0]}, expected 128x256')
    a0 = m.animations[0] if m.animations else None

    def key(anim, frame, b):
        rot, t = m.keys[anim.bank][b][anim.frames[frame][b]]
        return rot, t
    # height in the first pose (DW2 units)
    if a0 is not None:
        from dw2.model import world_matrices
        W = world_matrices(m, a0, 0)
    else:
        W = [np.eye(4) for _ in m.bones]
    ys = [(np.array(b.vertices, float) @ W[b.index][:3, :3].T + W[b.index][:3, 3])[:, 1] for b in m.bones if b.vertices]
    tall = float(-min(y.min() for y in ys))
    how = ''
    if height:
        S, how = height / tall, f'scaled to {height:.0f} units tall'
    elif scale:
        S, how = scale, 'given'
    else:
        S, how = measured_scale(code, log)
    info = dict(code=code, bones=B, dw2_height=round(tall), scale=round(S, 5), scale_how=how, height=round(tall * S))
    log(f'{code}: {B} bones, {tall:.0f} DW2 units tall -> x{S:.4f} ({how}) = {tall * S:.0f} DW1 units')
    # faces
    prims, owners = [], []
    for b in m.bones:
        for p in b.prims:
            uvs = [(min(max(u, 0), 127), min(max(v, 0), 255)) for u, v in p.uvs]
            if uvs != list(p.uvs):
                log(f'  note: bone {b.index}: a face samples outside the 128x256 page {list(p.uvs)}: clamped')
            prims.append(dict(uvs=uvs, clut=p.clut))
            owners.append(b.index)
    parts = tex_anim_parts(data, B)
    idx, new_uvs, moves, rinfo = repack(prims, src_idx, parts, log)
    info.update(rinfo)
    log(f'  texture: {rinfo["crossing_faces"]} faces cross row 128; windows at rows {rinfo["windows"]}, '
        f'{rinfo["left_over"]} faces in neither; layout {rinfo["mode"]}, '
        f'{rinfo["moved_islands"]} islands {"moved" if rinfo["mode"] == "halves" else "placed"}, '
        f'{rinfo["used_texels"]} of {SLOT_W * SLOT_H} texels used')
    if parts['cycles'] or parts['timed']:
        log(f'  note: {len(parts["cycles"])} cycling and {parts["timed"]} timed texture parts are not converted')
    info['tex_parts'] = dict(blinks=len(parts['blinks']), blinks_kept=len(moves), cycles=len(parts['cycles']),
                             timed=parts['timed'])
    # palettes
    cluts = sorted({p['clut'] for p in prims})
    pals = {k: [int(x) for x in hw[c >> 6, (c & 0x3F) * 16:(c & 0x3F) * 16 + 16]] for k, c in enumerate(cluts)}
    pal_of = {c: k for k, c in enumerate(cluts)}
    prim_pal = [pal_of[p['clut']] for p in prims]
    n0 = len(pals)
    merges = merge_palettes(idx, new_uvs, prim_pal, pals, maxp, log)
    final = sorted(pals)
    row = {p: k for k, p in enumerate(final)}
    # check: every face shows the same colours as in DW2 (texel by texel, through its palette)
    src_pal = {c: [int(x) for x in hw[c >> 6, (c & 0x3F) * 16:(c & 0x3F) * 16 + 16]] for c in cluts}
    bad = tot = 0
    err2 = 0.0
    for k, p in enumerate(prims):
        x0, y0, mk = footprint(p['uvs'])
        x1, y1, mk2 = footprint(new_uvs[k])
        a = np.array(src_pal[p['clut']])[src_idx[y0:y0 + mk.shape[0], x0:x0 + mk.shape[1]][mk]]
        b = np.array(pals[prim_pal[k]])[idx[y1:y1 + mk2.shape[0], x1:x1 + mk2.shape[1]][mk2]]
        diff = a != b
        bad += int(diff.sum())
        tot += int(mk.sum())
        err2 += sum(colour_dist2(int(x), int(y)) for x, y in zip(a[diff], b[diff]))
    info['texel_check'] = dict(face_texels=tot, differing=bad, rms_error=round(math.sqrt(err2 / max(tot, 1) / 3), 2))
    log(f'  texel check: {bad} of {tot} face texels differ from DW2 (rms {info["texel_check"]["rms_error"]}/255)')
    info['palettes'] = dict(dw2=n0, kept=len(final),
                            merged=[dict(src=a, into=b, faces=f, error=e) for a, b, f, e in merges])
    log(f'  palettes: {n0} -> {len(final)}' + (f' ({sum(1 for x in merges if x[3] == 0)} identical/exact)' if merges else ''))
    # bones
    bones = []
    k = 0
    for b in m.bones:
        bp = []
        for p in b.prims:
            bp.append(dict(verts=list(p.verts), norms=list(p.normals), uvs=[(int(u), int(v)) for u, v in new_uvs[k]],
                           row=row[prim_pal[k]], semi=bool(p.semi), abr=(p.tpage >> 5) & 3))
            k += 1
        if a0 is not None:
            rot, t = key(a0, 0, b.index)
            q, _s = decompose(rot)
        else:
            q, t = np.array([0, 0, 0, 1.0]), np.zeros(3)
        bones.append(dict(parent=b.parent, offset=tuple(float(x) * S for x in t), rest=tuple(float(x) for x in q),
                          verts=[tuple(float(x) * S for x in v) for v in b.vertices],
                          norms=[tuple(n) for n in b.normals], prims=bp))
    flat = bytearray(idx.astype(np.uint8).tobytes())
    # animations
    anims = {}
    def convert_frames(an):
        frames = []
        for f in range(len(an.frames)):
            fr = []
            for b in range(B):
                rot, t = key(an, f, b)
                q, s = decompose(rot)
                fr.append((tuple(float(x) for x in q), tuple(float(x) * S for x in t), tuple(float(x) for x in s)))
            frames.append(fr)
        return frames
    for an in m.animations:
        name = f'{an.bank}{an.slot}'
        a = mmdport.Anim(lambda an=an: convert_frames(an), FPS, an.loop_to is not None)
        a.loop_to = an.loop_to
        anims[name] = a
    model = mmdport.Model(code, bones, flat, [pals[p] for p in final], anims)
    model.blinks = moves
    model.info = info
    model.scale = S
    return model


def stats(model):
    nv = sum(len(set(tuple(int(round(x)) for x in v) for v in b['verts'])) for b in model.bones)
    q = sum(1 for b in model.bones for p in b['prims'] if len(p['verts']) == 4)
    t = sum(1 for b in model.bones for p in b['prims'] if len(p['verts']) == 3)
    mp = max(len(set(tuple(int(round(x)) for x in v) for v in b['verts'])) for b in model.bones)
    return dict(vertices=nv, primitives=q + t, quads=q, triangles=t, max_piece=mp, bones=len(model.bones) + 1,
                palettes=len(model.pals))


BUDGET = dict(vertices=706, primitives=713, max_piece=mmdport.MAX_VERTS_PER_OBJECT, bones=34, palettes=15)


def over_budget(st):
    return [k for k, v in BUDGET.items() if st[k] > v]


# ---------------------------------------------------------------- model edits (partner specs)
def _trs_matrix(q, t, s):
    R = mmd.quat_matrix(q)
    return [[R[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def _inv_affine(M):
    import numeric as np
    M = np.array(M, float)
    try:
        return np.linalg.inv(M)
    except np.linalg.LinAlgError:     # rule: a parent hidden in a frame by a zero scale (DW2003 Taomon, Kyukimon)
        return np.linalg.pinv(M)


def reparent(model, child, parent, log=print):
    """Hangs model bone `child` from model bone `parent` (two bones with the same parent, e.g.
    DW2's tail, a second root, under the pelvis), keeping every pose: the new local transform
    is inv(L_parent) . L_child at the rest pose and at every frame."""
    import numeric as np
    from dw2.gltf import decompose
    c, p = model.bones[child], model.bones[parent]
    if c['parent'] != p['parent'] or parent > child:
        raise SystemExit(f'reparent {child} -> {parent}: only a later sibling can be moved under a bone')

    def local(qp, tp, sp, qc, tc, sc):
        L = _inv_affine(_trs_matrix(qp, tp, sp)) @ np.array(_trs_matrix(qc, tc, sc), float)
        q, s = decompose(L[:3, :3])
        return tuple(float(x) for x in q), tuple(float(x) for x in L[:3, 3]), tuple(float(x) for x in s)
    q, t, _ = local(p.get('rest', mmdport.IDENTITY_Q), p['offset'], (1, 1, 1), c.get('rest', mmdport.IDENTITY_Q),
                    c['offset'], (1, 1, 1))
    c['rest'], c['offset'], c['parent'] = q, t, parent
    def edit(frames):
        for f in frames:
            f[child] = local(*f[parent], *f[child])
        return frames
    for a in model.anims.values():
        a.map_frames(edit)
    log(f'  bone {child + 1} now hangs from bone {parent + 1}')


def reorder(model, order):
    """Renumbers the bones: new bone k = old bone order[k] (parents must still come first)."""
    inv = {o: k for k, o in enumerate(order)}
    bones = [model.bones[o] for o in order]
    for b in bones:
        b['parent'] = inv[b['parent']] if b['parent'] >= 0 else -1
    model.bones = bones
    for a in model.anims.values():
        a.map_frames(lambda frames: [[f[o] for o in order] for f in frames])


def hub_roots(model, log=print):
    """Rule: DW2 models hang many pieces from the actor (a second root: Kimeramon's tail; Flymon has
    13 roots, Tortomon 7). In DW1 only the hips bone follows the hips motion of a retargeted
    animation, so every other root would stay behind when the body moves. The root with the most
    vertices (the body) becomes bone 1 and every other root is hung from it (`reparent`, every
    pose kept). Returns the old index of the hub, or None when there was one root already."""
    n = len(model.bones)
    roots = [i for i, b in enumerate(model.bones) if b['parent'] < 0]
    if len(roots) < 2:
        return None
    kids = {i: [j for j in range(n) if model.bones[j]['parent'] == i] for i in range(n)}

    def size(i):
        return len(model.bones[i]['verts']) + sum(size(j) for j in kids[i])
    hub = max(roots, key=lambda r: (size(r), -r))
    reorder(model, [hub] + [i for i in range(n) if i != hub])
    for r in range(1, len(model.bones)):
        if model.bones[r]['parent'] < 0:
            reparent(model, r, 0, lambda *a: None)
    log(f'  roots: {len(roots)} -> 1 (hub: old bone {hub + 1}, {size(hub)} vertices; the other roots hang from it)')
    return hub


def concat(model, name, parts):
    """A new animation made of others played one after the other (no loop)."""
    frames = [f for nm in parts for f in model.anims[nm].frames]
    a = mmdport.Anim(frames, model.anims[parts[0]].fps, False)
    a.loop_to = None
    model.anims[name] = a


def apply_spec_edits(model, spec, log=print):
    if spec.get('hub_roots'):
        hub_roots(model, log)
    for c, p in (spec.get('reparent') or {}).items():
        reparent(model, num(c) - 1, num(p) - 1, log)
    for nm, parts in (spec.get('concat') or {}).items():
        concat(model, nm, parts)
    if spec.get('meshfix') is not None:        # tools/meshfix.py: the mesh edits a batch spec records (same parameters, no search)
        import meshfix
        meshfix.apply(model, spec['meshfix'], log=log)


# ---------------------------------------------------------------- clips and blinks
def clip(model, name, loop=None, **kw):
    """mmdport.clip of a DW2 animation. A looping one gets its loop-start frame appended (the
    closing sample) and a speed that makes the loop body a whole number of DW1 ticks."""
    a = model.anims[name]
    if loop is None:
        loop = name in LOOPING and a.loop
    if not loop or kw.get('start') or kw.get('end') is not None:
        kw.setdefault('loop', False)
        return mmdport.clip(model, name, **kw)
    L = a.loop_to or 0
    n = len(a.frames)
    ticks = max(1, round((n - L) * 20 / a.fps))
    fps = (n - L) * 20 / ticks
    tmp = mmdport.Model(model.name, model.bones, model.idx, model.pals,
                        {name: mmdport.Anim(a.frames + [a.frames[L]], fps * kw.pop('speed', 1.0), True)})
    c = mmdport.clip(tmp, name, loop=True, **kw)
    c['loop_sample'] = round(L * 20 / fps)
    return c


def eye_events(model, state_at):
    """Texture moves for eye states: state_at [(sample, 0 open | 1 half | 2 closed)]."""
    out = []
    for s, k in state_at:
        for b in model.blinks:
            for d in b['dst']:
                out.append((s, 'tex', dict(src=b['src'][k], size=b['size'], dst=d)))
    return out


def blink_plan(n, loop_sample, closed=False, blink=False):
    """[(sample, state)]: the state at the start, and a blink (half, closed x2, half, open: 0.2 s
    as Gfx_AnimateModelTex) in the middle of a looping body of at least 24 ticks."""
    plan = [(0, 2 if closed else 0)]
    if blink and not closed and loop_sample is not None and n - loop_sample >= 24:
        f = loop_sample + (n - loop_sample) // 2
        plan += [(f, 1), (f + 1, 2), (f + 3, 1), (f + 4, 0)]
    return plan


def write_clips_gltf(path, model, clips, events):
    """mmdport.write_gltf plus extras.texture_moves (for mmd.import_anims gltf_events)."""
    g = mmdport.write_gltf(path, model, clips)
    for an in g.get('animations', []):
        ev = events.get(an['name'], [])
        if ev:
            ex = an.setdefault('extras', {})
            ex['texture_moves'] = [dict(tick=s, src=list(c['src']), size=list(c['size']), dst=list(c['dst']))
                                   for s, kind, c in ev]
            ex['sounds'] = []
    with open(path, 'w') as f:
        json.dump(g, f)


def convert(model, typ, out_mmd, out_tex, slots, gltf_path=None, tol=1, log=print):
    """Model -> MMD with the DW2 animations in `slots` {anim: [slot]} and blinks; the texture entry."""
    base = mmdport.base_mmd(model, typ, log)
    clips, maps, events = {}, {}, {}
    for name, ss in slots.items():
        if name not in model.anims:
            continue
        for s in ss:
            cname = f'{name}@{s:#04x}'
            c = clip(model, name)
            clips[cname] = c
            maps[cname] = s
            if model.blinks:
                n = len(c['frames'])
                ls = c['loop_sample']
                n_ticks = round((n - 1) * 20 / c['fps']) + 1
                events[cname] = eye_events(model, blink_plan(n_ticks - 1, ls, name in CLOSED_EYES,
                                                             s in BLINK_SLOTS))
    gltf_path = gltf_path or os.path.splitext(out_mmd)[0] + '.gltf'
    write_clips_gltf(gltf_path, model, clips, events)
    m, done = mmd.import_anims(base, gltf_path, maps, fps=20.0, tol=tol, only_mapped=True, gltf_events=True,
                               log=log)
    data = m.build()
    open(out_mmd, 'wb').write(data)
    open(out_tex, 'wb').write(mmdport.build_tim(model.idx, model.pals))
    for s, (name, n, ls, why, size) in sorted(done.items()):
        log(f'  slot {s:#04x} <- {name}: {n} ticks, {size} bytes' + (f', loops from {ls}' if ls is not None else ''))
    log(f'{out_mmd}: {len(data)} bytes; {out_tex}: texture entry')
    return data


# ---------------------------------------------------------------- texture moves into built animations
def insert_tex(an, frame, moves):
    """Adds texture-move instructions at `frame` of an encoded animation (after that frame's
    keyframe, adding an empty one if needed: a pending texture instruction would be taken as
    a loop start by tickAnimation's 0x1000 pre-check)."""
    ins = an.instrs
    frame = max(1, min(frame, an.frame_count))
    k = next((i for i, x in enumerate(ins) if x['op'] == 'key' and x['frame'] == frame), None)
    new = [dict(op='tex', frame=frame, src=tuple(m['src']), size=tuple(m['size']), dst=tuple(m['dst'])) for m in moves]
    if k is not None:
        ins[k + 1:k + 1] = new
        return True
    if any(x['op'] == 'loop_end' and x['frame'] == frame for x in ins):
        return False
    # before the first instruction of a later frame (a loop start belongs to the frame after it)
    pos = len(ins) - 1                       # before 'end'
    for i, x in enumerate(ins):
        f = x.get('frame')
        if x['op'] == 'loop_start':
            f = next((y.get('frame') for y in ins[i + 1:] if y.get('frame') is not None), None)
        if f is not None and f > frame:
            pos = i
            break
    ins[pos:pos] = [dict(op='key', frame=frame, bones=[])] + new
    return True


def add_eyes(m, model, slot_states, log=print):
    """slot_states {slot: [(frame, state)]}: texture moves of the model's blinks into slots of
    an MMD (in place). Slots that share an animation get it once."""
    done = set()
    for s, plan in sorted(slot_states.items()):
        if s >= len(m.anims.table) or m.anims.table[s] is None or m.anims.table[s] in done:
            continue
        an = m.anims.anims[m.anims.table[s]]
        done.add(m.anims.table[s])
        for f, k in plan:
            mv = [dict(src=b['src'][k], size=b['size'], dst=d) for b in model.blinks for d in b['dst']]
            if not insert_tex(an, f, mv):
                insert_tex(an, f + 1, mv)


def donor_eye_plan(src, src_t, slot, eyes):
    """The DW1 donor's eye states in a slot, mapped to DW2's open/half/closed through
    `eyes` {"src x,y": state} (texture moves to other rectangles are ignored)."""
    if slot >= len(src.anims.table) or src.anims.table[slot] is None:
        return None
    an = src.anims.anims[src.anims.table[slot]]
    out = []
    for x in an.instrs:
        if x['op'] == 'tex':
            k = eyes.get(f'{x["src"][0]},{x["src"][1]}')
            if k is not None:
                out.append((x['frame'], {'open': 0, 'half': 1, 'closed': 2}[k] if isinstance(k, str) else int(k)))
    return out or None


def build_partner(model, spec, out_mmd, out_tex, workdir, log=print):
    """mmdport.build_partner, then the blinks: the donor's eye states in the retargeted slots
    (spec "eyes": {"src": {"x,y": "open"|"half"|"closed"}}), DW2's rule in the clip slots
    (closed in hit/knock-back/lying clips, else open), a blink in the looping idles."""
    data = mmdport.build_partner(model, spec, out_mmd, out_tex, workdir, log)
    if not model.blinks:
        return data
    nb = len(model.bones) + 1
    m = mmd.MMD.parse(data, nb)
    m.type = num(spec['type'])
    src_t = num(spec['source']['type'])
    src = mmd.MMD.load(os.path.join(ROOT, spec['source']['mmd']), src_t)
    eyes = (spec.get('eyes') or {}).get('src', {})
    clips = {num(k): v for k, v in spec.get('clips', {}).items()}
    plans = {}
    for s, idx in enumerate(m.anims.table):
        if idx is None:
            continue
        an = m.anims.anims[idx]
        if s in clips:
            closed = clips[s]['anim'] in CLOSED_EYES or clips[s].get('eyes') == 'closed'
            plan = [(1, 2 if closed else 0)]
        else:
            ss = {num(t): num(f) for t, f in spec.get('slot_from', {}).items()}.get(s, s)
            plan = donor_eye_plan(src, src_t, ss, eyes) or [(1, 0)]
            if plan[0][0] != 1:
                plan.insert(0, (1, 0))
        if s in BLINK_SLOTS and all(k == 0 for _, k in plan):
            ls = mmd.anim_loops(an, nb)
            if ls is not None and an.frame_count - ls >= 24:
                f = ls + (an.frame_count - ls) // 2
                plan += [(f, 1), (f + 1, 2), (f + 3, 1), (f + 4, 0)]
        plans[s] = plan
    add_eyes(m, model, plans, log)
    data = m.build()
    if len(data) > mmdport.PARTNER_MMD_MAX:
        raise SystemExit(f'{out_mmd}: {len(data)} bytes with the blinks do not fit PARTNER_MODEL_BUFFER')
    open(out_mmd, 'wb').write(data)
    log(f'{out_mmd}: {len(data)} bytes with the blinks ({mmdport.PARTNER_MMD_MAX - len(data)} free)')
    return data


# ---------------------------------------------------------------- checks and previews
def roundtrip_ok(data, nb):
    """mmd.py roundtrip's two checks on one file: rebuilt byte for byte, and after decoding and
    re-encoding every primitive."""
    m = mmd.MMD.parse(data, nb)
    raw = m.build() == data
    for ob in m.tmd.objects:
        ob.prims = [mmd.Prim.encode(p.decode()) for p in ob.prims]
    return raw and m.build() == data


def render_ours(mmd_path, tim_path, typ, size, yaw_deg, slot=0, tick=0):
    """mmd.render of a converted model at a slot/tick (RGBA bytes)."""
    import retarget
    nb = mmd.exe().bone_count[typ]
    m = mmd.MMD.parse(open(mmd_path, 'rb').read(), nb)
    m.type = typ
    tim = mmd.Tim4(open(tim_path, 'rb').read())
    smp, _, _ = retarget.play(m.anims.anims[m.anims.table[slot]], nb, slot)
    pose = smp[min(tick, len(smp) - 1)]
    pose = [list(p) for p in pose]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return mmd.render(m, tim, pose, size, math.radians(yaw_deg))


def render_dw2(code, size, yaw_deg, anim=0, frame=0):
    _dw2()
    from dw2.model import load as dload, world_matrices
    from dw2.render import draw
    m = dload(model_path(code))
    W = world_matrices(m, m.animations[anim], frame)
    return draw(m, W, yaw_deg, size)


def _pil(rgba, size):
    from tools.image import Image
    return Image.frombytes('RGBA', (size, size), bytes(rgba)).convert('RGB')


# ---------------------------------------------------------------- commands
def _slots(spec_list):
    slots = {}
    for s in spec_list or []:
        nm, _, v = s.partition('=')
        slots[nm] = [int(x, 0) for x in v.split(',') if x]
    return slots or dict(DEFAULT_SLOTS)


def cmd_info(a):
    m = load(a.code, a.scale, a.height, a.max_palettes)
    st = stats(m)
    print(f'{st["bones"]} DW1 bones (with the entity), {st["vertices"]} vertices, {st["primitives"]} primitives '
          f'({st["quads"]} quads, {st["triangles"]} triangles), {st["palettes"]} palettes, '
          f'max {st["max_piece"]} vertices per piece; over the budgets: {", ".join(over_budget(st)) or "none"}')
    print(f'blinks: {len(m.blinks)} part(s) kept of {m.info["tex_parts"]["blinks"]}')
    for k, an in m.anims.items():
        print(f'  {k} ({KINDS.get(k, "?")}): {len(an.frames)} frames ({len(an.frames) * 20 / an.fps:.0f} DW1 ticks)'
              + (f', loops to frame {an.loop_to}' if an.loop else ''))


def cmd_convert(a):
    m = load(a.code, a.scale, a.height, a.max_palettes)
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, a.name or a.code)
    convert(m, a.type, stem + '.MMD', stem + '.TIM', _slots(a.slot), stem + '.gltf', a.tol)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
    st = stats(m)
    print(json.dumps(dict(st, over=over_budget(st), **{k: m.info[k] for k in ('scale', 'height', 'mode')})))


def species_record(model, spec, like, out_mmd, out_tex, log=print):
    """A species JSON (tools/species.py) for the partner: `like` (an existing record of the
    same Digimon, or of the donor) with this model's files, skeleton, boneCount and the donor's
    technique effect origins moved onto the new skeleton (import_batch.effect_origins: each
    EFE point of the donor's techniques goes from the donor bone to the mapped target bone,
    joint-relative, scaled by the height ratio)."""
    import import_batch as ib
    import collections, species
    rec = json.load(open(like), object_pairs_hook=collections.OrderedDict)   # a complete species file (docs/mods/species.md)
    T = ib.shape_of_model(model)
    Tw = ib.model_world_dw(model)
    donor = num(spec['source']['type'])
    S = ib.donor_shape(donor)[0]
    bmap = {int(k): (v[0] if isinstance(v, list) else v) for k, v in spec['map'].items() if not isinstance(v, str)}
    k = T.H / S.H
    otype = rec.get('effects_like', donor)
    moves = species.techniques_from_json(rec['techniques'], like)
    eo, cfx = ib.effect_origins(T, Tw, donor, otype, bmap, moves, k, log)
    rec['_source'] = (f'Digimon World 2 AAA/4.AAA/MODEL/{os.path.basename(os.path.dirname(model_path(model.name)))}/'
                      f'{model.name}.BIN (tools/dw2mmd.py partner {os.path.relpath(spec["_path"], ROOT)} '
                      f'{os.path.relpath(os.path.dirname(out_mmd), ROOT)})')
    m = rec.get('model', {})
    rec['model'] = collections.OrderedDict(file=os.path.relpath(out_mmd, ROOT), radius=m.get('radius', 100),
                                           height=int(round(T.H)), skeleton=[list(x) for x in mmdport.skeleton(model)])
    rec['texture'] = dict(file=os.path.relpath(out_tex, ROOT), entry=0)
    rec['_effect_origins'] = (f'{spec.get("_eo_note", "")}import_batch.effect_origins: every EFE origin of '
                              f'the techniques of type {otype} moved from the donor bone to the mapped one '
                              f'(x{k:.3f}, the height ratio)').strip()
    rec['effect_origins'] = spec.get('effectOrigins', eo)
    rec['condition_bubble'] = spec.get('conditionFx', cfx)
    if 'effectOrigins' in spec:
        rec['_effect_origins'] = spec.get('_effectOrigins', 'given in the partner spec')
    return rec


def cmd_partner(a):
    spec = json.load(open(a.spec))
    spec['_path'] = os.path.abspath(a.spec)
    m = load(spec['dw2'], spec.get('scale'), spec.get('height'), spec.get('max_palettes', MAX_PALETTES))
    apply_spec_edits(m, spec)
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, spec.get('name', m.name))
    build_partner(m, spec, stem + '.MMD', stem + '.TIM', a.out_dir)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
    json.dump(m.info, open(stem + '.info.json', 'w'), indent=1)
    if a.species:
        rec = species_record(m, spec, a.like, stem + '.MMD', stem + '.TIM')
        import species
        species.write_file(a.species, rec)
        print(f'{a.species}: species file (effect origins {rec["effect_origins"]}, condition {rec["condition_bubble"]})')


def cmd_sheet(a):
    """The source animations, posed frame by frame through the converted model (mmd.render)."""
    m = load(a.code, a.scale, a.height, log=lambda *x: None)
    typ = 250
    base = mmdport.base_mmd(m, typ, log=lambda *x: None)
    tim = mmd.Tim4(mmdport.build_tim(m.idx, m.pals))
    rows = []
    for k, an in m.anims.items():
        imgs = []
        for f in an.frames[::a.every]:
            pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
            prev = None
            for (q, t, s) in f:
                e = [round(x) for x in mmd.matrix_euler(mmd.quat_matrix(q), prev)]
                pose.append([round(x * 4096) for x in s] + e + [round(x) for x in t])
            imgs.append(mmd.render(base, tim, pose, a.size, math.radians(a.yaw)))
        rows.append(imgs)
    W = max(len(r) for r in rows) * a.size
    H = len(rows) * a.size
    out = bytearray([30, 30, 30, 255] * (W * H))
    for r, imgs in enumerate(rows):
        for c, im in enumerate(imgs):
            for y in range(a.size):
                o = ((r * a.size + y) * W + c * a.size) * 4
                out[o:o + a.size * 4] = im[y * a.size * 4:(y + 1) * a.size * 4]
    mmd.png_write(a.out, W, H, out)
    print(f'{a.out}: rows {list(m.anims)}')


def dw2_sources():
    return [r for r in csv.DictReader(open(SOURCES_CSV)) if r['model_from'] == 'DW2']


def safe(name):
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)


def batch_one(r, out_root, size=150, log=print):
    """Converts one DW2-source Digimon into imported/<Name>/mmd/ and checks it."""
    name, code = r['name'], r['model_id']
    d = os.path.join(out_root, safe(name), 'mmd')
    os.makedirs(d, exist_ok=True)
    stem = os.path.join(d, safe(name))
    rep = dict(name=name, code=code)
    lines = []
    lg = lambda *x: lines.append(' '.join(str(y) for y in x))
    try:
        m = load(code, log=lg)
        st = stats(m)
        rep.update(stats=st, over=over_budget(st), info=m.info)
        data = convert(m, 250, stem + '.MMD', stem + '.TIM', dict(DEFAULT_SLOTS), stem + '.gltf', 1, lg)
        json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
        nb = len(m.bones) + 1
        rep['mmd_bytes'] = len(data)
        rep['roundtrip'] = roundtrip_ok(data, nb)
        mm = mmd.MMD.parse(data, nb)
        rep['slots'] = [hex(s) for s, x in enumerate(mm.anims.table) if x is not None]
        # previews, same yaw: DW2's renderer of A0 frame 0, ours of slot 0 tick 0
        ours = _pil(render_ours(stem + '.MMD', stem + '.TIM', 250, size, 30), size)
        theirs = render_dw2(code, size, 30)
        ours.save(stem + '-preview.png')
        theirs.save(stem + '-dw2.png')
        rep['ok'] = True
    except SystemExit as ex:
        rep['ok'], rep['error'] = False, str(ex)
    except Exception as ex:
        import traceback
        rep['ok'], rep['error'] = False, f'{type(ex).__name__}: {ex}'
        lines.append(traceback.format_exc())
    open(stem + '.log', 'w').write('\n'.join(lines) + '\n')
    json.dump(rep, open(stem + '.report.json', 'w'), indent=1, default=str)
    return rep


def _batch_worker(args):
    r, out_root = args
    import io
    sys.stdout = io.StringIO()
    return batch_one(r, out_root)


def cmd_batch(a):
    rows = dw2_sources()
    if a.names:
        rows = [r for r in rows if r['name'] in a.names]
    out_root = a.out or IMPORTED
    if a.jobs > 1:
        from multiprocessing import Pool
        with Pool(a.jobs) as p:
            reps = p.map(_batch_worker, [(r, out_root) for r in rows], chunksize=1)
    else:
        reps = [batch_one(r, out_root) for r in rows]
    # summary
    auto = [x for x in reps if x.get('ok') and x.get('roundtrip') and not x.get('over')
            and x['info']['palettes']['kept'] <= MAX_PALETTES]
    print(f'{len(reps)} Digimon: {sum(1 for x in reps if x.get("ok"))} converted, {len(auto)} fully automatic '
          f'(within every budget, round trip identical)')
    for x in reps:
        if not x.get('ok'):
            print(f'  {x["name"]:16} FAILED: {x.get("error")}')
            continue
        i = x['info']
        mg = i['palettes']['merged']
        lossy = [g for g in mg if g['error'] > 0]
        lossy_note = (' (' + ', '.join(f"{g['faces']}f err {g['error']}" for g in lossy) + ')') if lossy else ''
        print(f'  {x["name"]:16} {x["code"]} h{i["height"]:4} {i["mode"]:8} cross {i["crossing_faces"]:3} '
              f'win {i["windows"][0]:3},{i["windows"][1]:3} left {i["left_over"]:3} moved {i["moved_islands"]:3} pal {i["palettes"]["dw2"]:2}->{i["palettes"]["kept"]:2}'
              f'{lossy_note} '
              f'texels {i["texel_check"]["differing"]}/{i["texel_check"]["face_texels"]} blinks {i["tex_parts"]["blinks_kept"]}/{i["tex_parts"]["blinks"]} prims {x["stats"]["primitives"]} '
              f'verts {x["stats"]["vertices"]} bones {x["stats"]["bones"]} {x["mmd_bytes"]} B '
              f'rt {"ok" if x["roundtrip"] else "DIFF"}{" OVER " + ",".join(x["over"]) if x["over"] else ""}')
    json.dump(reps, open(os.path.join(ROOT, 'build', 'dw2', 'batch-report.json'), 'w'), indent=1, default=str)
    if a.sheet:
        contact_sheet([x for x in reps if x.get('ok')], out_root, a.sheet)


def contact_sheet(reps, out_root, path, size=150, cols=4):
    from tools.image import Image, ImageDraw
    cell_w, cell_h = 2 * size, size + 14
    rows = (len(reps) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell_w, rows * cell_h), (20, 20, 24))
    dr = ImageDraw.Draw(sheet)
    for k, x in enumerate(reps):
        stem = os.path.join(out_root, safe(x['name']), 'mmd', safe(x['name']))
        X, Y = (k % cols) * cell_w, (k // cols) * cell_h
        sheet.paste(Image.open(stem + '-dw2.png').convert('RGB').resize((size, size)), (X, Y + 14))
        sheet.paste(Image.open(stem + '-preview.png').convert('RGB'), (X + size, Y + 14))
        dr.text((X + 3, Y + 1), f'{x["name"]}  DW2 | DW1 MMD', fill=(230, 230, 230))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sheet.save(path)
    print(f'{path}: {len(reps)} pairs (left DW2\'s own renderer, right the converted MMD)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--height', type=float); p.add_argument('--scale', type=float)
        p.add_argument('--max-palettes', type=int, default=MAX_PALETTES)
    p = sub.add_parser('info'); p.add_argument('code'); common(p); p.set_defaults(f=cmd_info)
    p = sub.add_parser('convert'); p.add_argument('code'); p.add_argument('type', type=lambda s: int(s, 0))
    p.add_argument('out_dir'); common(p); p.add_argument('--tol', type=int, default=1); p.add_argument('--name')
    p.add_argument('--slot', action='append', help='A0=0,0x21 (DW2 animation = DW1 slots)'); p.set_defaults(f=cmd_convert)
    p = sub.add_parser('partner'); p.add_argument('spec'); p.add_argument('out_dir')
    p.add_argument('--species', help='also write a species JSON (tools/species.py) here')
    p.add_argument('--like', help='the species JSON it starts from (name, stats, moves, partner data)')
    p.set_defaults(f=cmd_partner)
    p = sub.add_parser('sheet'); p.add_argument('code'); p.add_argument('out'); common(p)
    p.add_argument('--every', type=int, default=6); p.add_argument('--size', type=int, default=120)
    p.add_argument('--yaw', type=float, default=30.0); p.set_defaults(f=cmd_sheet)
    p = sub.add_parser('batch'); p.add_argument('names', nargs='*'); p.add_argument('--out')
    p.add_argument('--jobs', type=int, default=4); p.add_argument('--sheet', default=os.path.join(ROOT, 'build', 'dw2', 'dw2-vs-dw1.png'))
    p.set_defaults(f=cmd_batch)
    a = ap.parse_args()
    _dw2()
    a.f(a)


if __name__ == '__main__':
    main()
