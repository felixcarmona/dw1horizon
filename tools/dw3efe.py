#!/usr/bin/env python3
"""A Digimon World 2003 technique's 3D effects as a Digimon World effect chunk, through the DW2 converter.

tools/dw3effect.py reads the technique (the caster's model script) and turns each 3D effect it spawns (a
MEFT file) into a dw2effect.Effect already in the caster's frame: the spawn's position and turn and the turn
from the field's frame are in its root keys, and a later spawn starts with hidden frames. Every such effect
goes to tools/dw2efe.py as a cast object at the caster's feet (DW2 slot 2, no offset of its own), so the
converter's own rules apply: an object that flies most of the way to the other row is a traveller that flies
to its target and deals the hit there; otherwise the hit comes when the objects end.

Scale: the field's (FIELD_SCALE, this game's distance between the fighters over DW2003's), so an effect covers
the same share of the field as on the disc: a beam that crosses DW2003's field crosses this game's. (The
species' import scale, --scale-from-species, keeps it at its size against the caster instead, which leaves a
large species' effect a quarter of the field.) Textures are halved (dw2efe's half=True).

Length: the whole effect. DW2 shows a cast object two seconds (dw2efe.CAST_FRAMES); a DW2003 effect runs as
long as its frames. When the whole effect does not fit a chunk, the longest opening that fits is kept and
info['kept'] / info['frames'] say how much; leave_out (--leave-out) instead drops named parts and keeps the
whole length, and info['left_out'] names them.

Fidelity: compare() renders the original and the conversion from the same camera (framing the fighters and
the effect, scaled with the field) and fidelity() measures them frame by frame; passes() is the check a
conversion must meet before it is shown. The measures see area, light, timing and place, not shape: a thin
part (a ring of runes) can be missing and still pass, so a conversion that leaves parts out says so.

    python3 tools/dw3efe.py --disc DW3.bin convert M372SGRG 11 --like 63 --out chunk.bin
    python3 tools/dw3efe.py --disc DW3.bin compare M372SGRG 11 --like 63 --mp4 out.mp4   (exits 1 when unfaithful)
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools import dw3effect as X            # noqa: E402
from tools import dw2effect as D            # noqa: E402
from tools import dw2efe as C               # noqa: E402

ROOT = X.ROOT
CHUNK_SIZE = 0x5000
FEET = 2                                     # DW2 slot 2: the caster's feet, no offset
DEFAULT_SCALE = 0.15                         # about the median import scale, for a species with no spec
# Effect chunk ids, one per imported species (its key), so batches of conversions never collide: the 3D
# effects take 196-222 and the sprite-only techniques 223-250 (the loader takes ids below 378).
MEFT_KEYS = (295, 297, 298, 299, 300, 302, 303, 310, 312, 313, 316, 317, 318, 323, 326, 327, 329, 333, 334, 335,
             352, 405, 406, 407, 408, 430, 433)
SPRITE_KEYS = (296, 304, 305, 306, 307, 308, 309, 311, 314, 315, 319, 320, 321, 322, 324, 325, 328, 330, 331, 332,
               336, 351, 353, 354, 403, 404, 409, 432)
EFFECT_IDS = {**{k: 196 + n for n, k in enumerate(MEFT_KEYS)}, **{k: 223 + n for n, k in enumerate(SPRITE_KEYS)}}

DW1_ROWS = 2700                              # this game's distance between the two fighters (the comparisons)
FIELD_SCALE = DW1_ROWS / (2 * X.FIELD_HALF)


def import_scale(name, root=ROOT):
    path = os.path.join(root, 'content', 'imports', 'specs', f'{name}.json')
    if os.path.isfile(path):
        s = json.load(open(path)).get('scale')
        if s:
            return float(s)
    return DEFAULT_SCALE


def launch_table(chunk):
    from tools.derive.steps.effects import launch_table as lt
    return lt(chunk)


def native_chunk(efe, index):
    return bytes(efe[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE])


def remap_palettes(pals, hists, rows=C.PALETTE_ROWS):
    """dw2efe.reduce_palettes without averaging: two palettes share a row only by remapping one's texels to
    the nearest colours (of the same kind: transparent, solid, blending) the other already draws. A sprite's
    palettes are often one colour cycle (the same picture lit differently), where averaging two would light
    a ring's dark middle; remapping keeps each texel's own brightness. Returns what reduce_palettes does."""
    groups = [C.Group(p, h) for p, h in zip(pals, hists)]
    member = [(i, tuple(range(16))) for i in range(len(pals))]
    while len(groups) > rows:
        best = None
        for i, gi in enumerate(groups):
            for j, gj in enumerate(groups):
                if i == j:
                    continue
                mp, cost = list(range(16)), 0
                for k in range(16):
                    if not gj.hist[k]:
                        continue
                    same = [x for x in range(16) if C._stp(gi.cols[x]) == C._stp(gj.cols[k]) and (gi.hist[x] or x == k)]
                    if not same:
                        cost = None
                        break
                    mp[k] = min(same, key=lambda x: C._d2(gi.cols[x], gj.cols[k]))
                    cost += gj.hist[k] * C._d2(gi.cols[mp[k]], gj.cols[k])
                if cost is not None and (best is None or cost < best[0]):
                    best = (cost, i, j, mp)
        if best is None:
            raise C.Unconvertible(f'effect: {len(groups)} palettes and no two can share a row')
        _cost, i, j, mp = best
        gi, gj = groups[i], groups[j]
        for k in range(16):
            if gj.hist[k] and not gi.hist[mp[k]]:
                gi.cols[mp[k]] = gj.cols[k]
            gi.hist[mp[k]] += gj.hist[k]
        member = [((i if g == j else g), tuple(mp[x] for x in m) if g == j else m) for g, m in member]
        del groups[j]
        member = [((g - 1 if g > j else g), m) for g, m in member]
    return [tuple(g.cols) for g in groups], member


def _convert(casts, origin_table, effect_id, scale, area, n_hits, half, cap, aim, remap=False):
    keep = C.CAST_FRAMES, C.TRAVEL, C.reduce_palettes
    C.CAST_FRAMES = cap
    if not aim:
        C.TRAVEL = float('inf')          # no traveller: every part plays as on the disc, through the hit
    if remap:
        C.reduce_palettes = remap_palettes
    try:
        return C.convert_skill(casts, [], origin_table, effect_id, scale, area=area, n_hits=max(1, n_hits),
                               half=half)
    finally:
        C.CAST_FRAMES, C.TRAVEL, C.reduce_palettes = keep


def _name(spawn):
    return f'MEFT{spawn.id:04d}' if spawn.kind == 'meft' else f'sprite {spawn.id}'


def convert(disc, tables, tech, scale, origin_table, effect_id, area=False, n_hits=1, half=True, full_length=True,
            aim=False, leave_out=(), sprites=None):
    """(chunk, info) of the technique's 3D effects; dw2efe.Unconvertible when they do not fit a chunk.
    full_length: every frame of the effect (else DW2's two seconds); when that does not fit, the longest
    opening that does (info['kept'] frames of info['frames']).
    aim: DW2's travellers (a part that flies far is re-aimed at the target and vanishes at the hit). Off by
    default: a DW2003 beam or shot keeps drawing through and after its hit, so the effect plays as on the
    disc, sized for fighters DW1_ROWS apart, and the hit comes when the converter's cast ends.
    leave_out: (spawn index, bone) pairs whose faces are not carried, for an effect too large for one chunk;
    info['left_out'] names them. A conversion that leaves parts out is a composition, not the whole effect.
    sprites: carry the technique's sprites too, as flat quads (dw3sprite.effect); by default only when it has
    no 3D effect."""
    if sprites is None:
        sprites = not X.staged_effects(disc, tables, tech)
    _first, staged = X.staged_all(disc, tables, tech, sprites)
    if not staged:
        raise C.Unconvertible('technique: no 3D effect or sprite')
    left_out = []
    for i, b in leave_out:
        s, e = staged[i]
        left_out.append(f'{_name(s)} part {b} ({len(e.bones[b].prims)} faces)')
        e.bones[b] = D.Bone(e.bones[b].parent, e.bones[b].vertices, [])
    casts = [(FEET, e) for _s, e in staged]
    frames = max(len(e.frames) for _s, e in staged)
    if not full_length:
        frames = min(frames, C.CAST_FRAMES)
    try:
        chunk, info = _convert(casts, origin_table, effect_id, scale, area, n_hits, half, frames, aim, sprites)
        kept = frames
    except C.Unconvertible:
        lo, hi, best = 1, frames - 1, None          # the longest opening that fits
        while lo <= hi:
            mid = (lo + hi) // 2
            try:
                best = (mid, _convert(casts, origin_table, effect_id, scale, area, n_hits, half, mid, aim, sprites))
                lo = mid + 1
            except C.Unconvertible:
                hi = mid - 1
        if best is None:
            raise
        kept, (chunk, info) = best
    info['objects'] = [_name(s) for s, _e in staged]
    info['frames'], info['kept'] = frames, kept
    if left_out:
        info['left_out'] = left_out
    return chunk, info


# ------------------------------------------------------------------ fidelity

def _masks(frames, tol=48):
    """Per frame: (drawn, bright) pixel masks. Drawn = differs from the side's scenery, each pixel's most common
    colour over the clip (the floor, the fighters' markers), so scenery one renderer draws and the other does
    not is not counted; bright = a channel at 200 or more."""
    import numpy as np
    w, h = frames[0].width, frames[0].height
    a = np.stack([np.frombuffer(f.convert('RGB').tobytes(), np.uint8).reshape(h, w, 3) for f in frames])
    packed = (a[..., 0].astype(np.int32) << 16) | (a[..., 1].astype(np.int32) << 8) | a[..., 2]
    srt = np.sort(packed, axis=0)
    # the most common value per pixel: the longest run in the sorted column
    n = len(frames)
    change = np.vstack([np.ones((1, h, w), bool), srt[1:] != srt[:-1]])
    idx = np.where(change, np.arange(n)[:, None, None], 0)
    start = np.maximum.accumulate(idx, axis=0)
    run = np.arange(n)[:, None, None] - start + 1
    best = np.take_along_axis(srt, run.argmax(axis=0)[None], axis=0)[0]
    bg = np.stack([(best >> 16) & 255, (best >> 8) & 255, best & 255], axis=-1).astype(np.int32)
    drawn = np.abs(a.astype(np.int32) - bg[None]).sum(axis=-1) > tol
    bright = a.max(axis=-1) >= 200
    return drawn, bright


def _box(mask):
    import numpy as np
    ys, xs = np.nonzero(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return 0.0
    return float(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5)


def _corr_near(a, b):
    """The best correlation of the two curves with the conversion shifted by one frame either way or not at
    all: less than one tick of the 20 Hz effect engine, as for the boxes."""
    return max(_corr(a, b), _corr(a[1:], b[:-1]), _corr(a[:-1], b[1:])) if len(a) > 2 else _corr(a, b)


def fidelity(src, dst, active=0.002):
    """Frame-by-frame measures of a conversion against its original, both rendered from the same camera (of the
    same size):
    coverage (share of the picture drawn), bright area, the drawn bounding box, and over the frames where the
    original draws something: how many the conversion leaves (nearly) empty, the ratio of drawn area, the
    correlation of the two coverage curves (the best of the conversion a frame early, on time or a frame late) and the mean overlap (IoU) of the drawn bounding boxes. A box is
    matched with the conversion's box one frame before, at or after: the effect engine runs at 20 Hz, so a
    moving part can be a frame early or late in a 30 fps video."""
    n = min(len(src), len(dst))
    (sd, sb), (dd, db) = _masks(src[:n]), _masks(dst[:n])
    px = sd[0].size
    boxes = [_box(dd[k]) for k in range(n)]
    rows = [dict(cov=(sd[k].sum() / px, dd[k].sum() / px), bright=(sb[k].sum() / px, db[k].sum() / px),
                 box=(_box(sd[k]), boxes[k]), near=boxes[max(0, k - 1):k + 2]) for k in range(n)]
    act = [r for r in rows if r['cov'][0] > active]
    if not act:
        return dict(frames=len(rows), active=0, empty=0.0, area=1.0, bright=1.0, corr=1.0, iou=1.0, rows=rows)

    def iou(p, q):
        if not p or not q:
            return 0.0
        ix = max(0, min(p[2], q[2]) - max(p[0], q[0]))
        iy = max(0, min(p[3], q[3]) - max(p[1], q[1]))
        inter = ix * iy
        union = (p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - inter
        return inter / union if union else 0.0
    s_cov = sum(r['cov'][0] for r in act)
    s_br = sum(r['bright'][0] for r in act)
    return dict(frames=len(rows), active=len(act),
                empty=sum(r['cov'][1] < 0.1 * r['cov'][0] for r in act) / len(act),
                area=sum(r['cov'][1] for r in act) / s_cov,
                bright=sum(r['bright'][1] for r in act) / s_br if s_br else 1.0,
                corr=_corr_near([r['cov'][0] for r in rows], [r['cov'][1] for r in rows]),
                iou=sum(max(iou(r['box'][0], q) for q in r['near']) for r in act) / len(act), rows=rows)


def smoothness(src, dst, active=0.002, engine_rate=1 / 3):
    """How often the conversion's picture changes against the original's, both 60 fps (one frame a DW2003
    tick): over the pairs of frames where the original draws, the share in which each picture changes, the
    conversion's over the original's, capped at the effect engine's rate (20 Hz: a third of the frames). 1.0
    is as smooth as the engine can be; an effect that holds each pose two ticks scores about 0.5, and parts
    the conversion quantises or leaves still lower it a little (SlashAngemon, every tick, 0.74)."""
    import numpy as np
    n = min(len(src), len(dst))
    a = [np.asarray(f, dtype=np.int16) for f in src[:n]]
    b = [np.asarray(f, dtype=np.int16) for f in dst[:n]]
    pairs = [k for k in range(1, n) if (a[k].max(axis=2) > 8).mean() > active]
    if not pairs:
        return 1.0
    moved = lambda fr, k: np.abs(fr[k] - fr[k - 1]).max() > 8
    rs = sum(moved(a, k) for k in pairs) / len(pairs)
    rd = sum(moved(b, k) for k in pairs) / len(pairs)
    return min(1.0, rd / min(rs, engine_rate)) if rs else 1.0


LIMITS = dict(empty=0.25, area=0.5, area_max=2.0, bright=0.5, bright_max=3.0, corr=0.7, iou=0.5, smooth=0.65)


def passes(f, limits=LIMITS):
    """(ok, reasons): the conversion fails when it leaves the original's frames empty, draws much less or much
    more, much darker or brighter, does not follow the original over time, or draws somewhere else."""
    why = []
    if f['empty'] > limits['empty']:
        why.append(f"empty in {f['empty']:.0%} of the original's frames")
    if f['area'] < limits['area']:
        why.append(f"draws {f['area']:.0%} of the original's area")
    if f['area'] > limits['area_max']:
        why.append(f"draws {f['area']:.0%} of the original's area")
    if f['bright'] < limits['bright'] or f['bright'] > limits['bright_max']:
        why.append(f"bright area {f['bright']:.0%} of the original's")
    if f['corr'] < limits['corr']:
        why.append(f"coverage over time correlates {f['corr']:.2f}")
    if f['iou'] < limits['iou']:
        why.append(f"drawn boxes overlap {f['iou']:.2f}")
    if f.get('smooth', 1.0) < limits['smooth']:
        why.append(f"changes {f['smooth']:.0%} as often as the effect engine allows")
    return not why, why


# ------------------------------------------------------------------ comparison videos

def _one_side(tmd_objects):
    """efesim.tmd_objects keeping one face of each pair drawn both ways round: the converter writes a flat part
    twice, once per side, for the game's back-face culling, which efesim does not do (drawing both would
    double an additive part's light in the preview; the chunk keeps both)."""
    def wrapped(chunk):
        out = []
        for verts, prims in tmd_objects(chunk):
            seen, kept = set(), []
            for p in prims:
                k = (tuple(sorted(p[0])), tuple(sorted(map(tuple, p[1]))), p[2], p[3])
                if k not in seen:
                    seen.add(k)
                    kept.append(p)
            out.append((verts, kept))
        return out
    return wrapped


def converted_frames(chunk, ticks, width, height, cam, caster_height=600):
    """The chunk run in efesim, caster facing its target DW1_ROWS away (a fighter of the origin table's
    first type, so the launch point applies)."""
    from tools import efesim as S
    if not getattr(S.tmd_objects, 'one_side', False):
        S.tmd_objects = _one_side(S.tmd_objects)
        S.tmd_objects.one_side = True
    kind = struct.unpack_from('<h', launch_table(chunk))[0]
    f = [None] * 10
    f[1] = S.Fighter(kind, (0, 0, 0), 0, height=caster_height)
    f[2] = S.Fighter(kind, (0, 0, -DW1_ROWS), 0x800, height=caster_height)
    sim = S.Sim(chunk, f, 1, 2)
    last = max(ticks)
    for _ in range(last + 1):
        sim.step(reset_hits=True)
    from tools import image as img
    out = []
    for t in ticks:
        px = S.render(chunk, sim, t, cam)
        out.append(img.frombytes('RGB', (width, height), bytes(c for p in px for c in p)))
    return out, sim


def label(frame, text):
    from tools import image as img
    d = img.ImageDraw.Draw(frame)
    d.text((8, 6), text, fill=(240, 240, 240), font=img.ImageFont.load_default(size=max(14, frame.height // 12)))
    return frame


def framing(objs, width, height, home=None, fov=0.95):
    """(eye, look) of a side camera that holds both fighters and the effect's drawn points (2nd to 98th
    percentile over its life, so one stray far point does not shrink the rest), from the usual direction."""
    import math
    import numpy as np
    home = 2 * X.FIELD_HALF if home is None else home
    ys, zs = [0, -2000], [0, -home]
    for ob in objs:
        e = ob.effect
        for frame in range(0, len(e.frames), 2):
            for (r, t), bone in zip(D.world(e, frame), e.bones):
                if D.scale_of(r) < 1e-3 or not bone.prims:
                    continue
                for v in bone.vertices:
                    ys.append(t[1] + sum(r[1][k] * v[k] for k in range(3)))
                    zs.append(t[2] + sum(r[2][k] * v[k] for k in range(3)))
    y0, y1 = np.percentile(ys, [2, 98])
    z0, z1 = np.percentile(zs, [2, 98])
    y0, y1, z0, z1 = min(y0, -2000), max(y1, 0), min(z0, -home), max(z1, 0)
    look = (0, (y0 + y1) / 2, (z0 + z1) / 2)
    tan_h = math.tan(fov / 2)
    tan_v = tan_h * height / width
    dist = 1.15 * max((z1 - z0) / 2 / tan_h, (y1 - y0) / 2 / tan_v)
    d = (14000, -2200)                                   # the usual view: from the side, a little above
    n = math.hypot(*d)
    return (dist * d[0] / n, look[1] + dist * d[1] / n, look[2]), look


def _blend_onto(frame, a, centre, mode):
    """Draw an RGBA picture (alpha 255 = solid, 128 = the STP bit) centred at `centre` on an int32 RGB frame:
    solid texels cover, STP texels blend by `mode` (None: the frame is opaque, they cover too)."""
    import numpy as np
    H, W = frame.shape[:2]
    x0, y0 = int(round(centre[0] - a.shape[1] / 2)), int(round(centre[1] - a.shape[0] / 2))
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + a.shape[1]), min(H, y0 + a.shape[0])
    if fx0 >= fx1 or fy0 >= fy1:
        return
    src = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    dst = frame[fy0:fy1, fx0:fx1]
    rgb, al = src[..., :3].astype(np.int32), src[..., 3]
    cover, semi = (al > 0, np.zeros_like(al, bool)) if mode is None else (al == 255, al == 128)
    dst[cover] = rgb[cover]
    if mode == 1:
        dst[semi] = np.minimum(255, dst[semi] + rgb[semi])
    elif mode == 2:
        dst[semi] = np.maximum(0, dst[semi] - rgb[semi])
    elif mode == 3:
        dst[semi] = np.minimum(255, dst[semi] + rgb[semi] // 4)
    else:
        dst[semi] = (dst[semi] + rgb[semi]) // 2


def sprite_overlay(frames, disc, tables, tech, cam, ticks, pixel=None):
    """Draw the technique's sprites onto source frames (one per 60 Hz tick in `ticks`) as the screen sprites
    they are: each block's frame picture at its anchor's projection, sized by its depth (dw3sprite.PIXEL
    field units per pixel at that depth), turned and scaled by its channels, its right toward the target.
    Colours with the semi-transparency bit blend by the frame's rate (its word b); the others cover.
    This does not use dw3sprite.effect: it is the independent side of the fidelity check."""
    import numpy as np
    from tools import dw3sprite as P
    pixel = P.PIXEL if pixel is None else pixel
    sign = X.caster_sign(tech)
    flip = -1 if sign < 0 else 1
    out = [np.asarray(f.convert('RGB'), np.int32).copy() for f in frames]
    for s in X.sprite_spawns(tables, tech):
        try:
            pack, blocks = P.sprite_blocks(disc, tables, s.id)
        except (ValueError, KeyError, IndexError, struct.error):
            continue
        p = X.sprite_anchor(s, sign, pixel)
        anchor = (flip * p[0], p[1], flip * p[2] - X.FIELD_HALF)
        for n, t in enumerate(ticks):
            k = t - s.tick                       # block entries are 1/60 s ticks, like the script's
            if k < 0:
                continue
            for b in blocks:
                st = b.at(k)
                if st is None:
                    continue
                fr = pack.frames.get(st['frame'])
                layers = pack.frame_layers(st['frame'], stp_alpha=128, pal=st['pal'])
                sx, sy = b.flat_scale(st)
                mode = P.blend_of(pack, st['frame']) if fr else None
                if not layers or abs(sx) < 1e-3 or abs(sy) < 1e-3:
                    continue
                c = (anchor[0], anchor[1] + st['y'] * pixel, anchor[2] - st['x'] * pixel)
                pr = cam.project(c)
                right = cam.project((c[0], c[1], c[2] - pixel))
                if pr is None or right is None:
                    continue
                ppx = cam.focal * pixel / pr[2]
                mirror = right[0] < pr[0]
                for im in layers:                        # each part its own primitive: blended parts add up
                    w, h = im.size
                    nw, nh = max(1, int(round(w * abs(sx) * ppx))), max(1, int(round(h * abs(sy) * ppx)))
                    if nw > 4 * cam.w or nh > 4 * cam.h:
                        continue
                    im = im.resize((nw, nh), P.Image.NEAREST)
                    if (sx < 0) != mirror:
                        im = im.transpose(P.Image.FLIP_LEFT_RIGHT)
                    if sy < 0:
                        im = im.transpose(P.Image.FLIP_TOP_BOTTOM)
                    if st['rot'] % 4096:
                        im = im.rotate((1 if mirror else -1) * st['rot'] * 360.0 / 4096, P.Image.NEAREST,
                                       expand=True)
                    _blend_onto(out[n], np.asarray(im), pr, mode)
    from tools import image as img
    return [img.fromarray(f.astype(np.uint8), 'RGB') for f in out]


def compare(disc, tables, tech, chunk, title, width=480, height=270, sprites=None):
    """(frames, fidelity): source | converted at 60 fps (a frame per DW2003 tick; the converted side shows each
    20 Hz engine tick three frames, as the game does), the DW2003 effect on its own field and the chunk in
    efesim, from the same camera scaled with the field. The camera frames the fighters and the effect. The
    frame measures run on every second frame (30 fps), smoothness on all of them."""
    from tools import image as img
    sprites = not X.staged_effects(disc, tables, tech) if sprites is None else sprites
    objs = X.stage(disc, tables, tech)
    allobjs = X.stage(disc, tables, tech, sprites)        # the sprites as quads: only to frame and time them
    begin = min(o.start for o in allobjs)
    end = max(o.start + o.ticks for o in allobjs)
    eye, look = framing(allobjs, width, height)           # the caster's frame, the whole effect in view
    src_cam = D.Camera(width, height, eye=eye, look=look)
    src = X.render_frames(objs, range(begin, end), width, height, src_cam)
    if sprites:
        src = sprite_overlay(src, disc, tables, tech, src_cam, list(range(begin, end)))
    n = len(src)
    k = DW1_ROWS / (2 * X.FIELD_HALF)
    dst_cam = D.Camera(width, height, eye=tuple(v * k for v in eye), look=tuple(v * k for v in look))
    D.HOME_DISTANCE = DW1_ROWS
    dst, _sim = converted_frames(chunk, list(range(1, n // 3 + 2)), width, height, dst_cam)
    # the effect engine ticks at 20 Hz: each of its frames shows for three DW2003 ticks
    dst = [dst[min(len(dst) - 1, k // 3)] for k in range(n)]
    fid = fidelity(src[::2], dst[::2])
    fid['smooth'] = smoothness(src, dst)
    out = []
    for k in range(n):
        f = img.new('RGB', (2 * width + 4, height), (0, 0, 0))
        f.paste(label(src[k], f'{title}  DW2003'), (0, 0))
        f.paste(label(dst[k].copy(), 'converted (DW1)'), (width + 4, 0))
        out.append(f)
    return out, fid


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--disc')
    p.add_argument('--efe', default=os.path.join(ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE'))
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('convert', 'compare'):
        s = sub.add_parser(name)
        s.add_argument('model')
        s.add_argument('slot', type=int)
        s.add_argument('--like', type=int, required=True, help='the native chunk whose launch point it takes')
        s.add_argument('--species', help='import spec name (with --scale-from-species)')
        s.add_argument('--scale', type=float, help=f'default: the field scale, {FIELD_SCALE:.4f}')
        s.add_argument('--scale-from-species', action='store_true', help="the species' import scale instead")
        s.add_argument('--two-seconds', action='store_true', help="DW2's cast length instead of the whole effect")
        s.add_argument('--area', action='store_true', help='the technique hits every enemy')
        s.add_argument('--full-texture', action='store_true', help='keep the texture at its full size')
        s.add_argument('--aim', action='store_true', help="DW2's travellers: re-aim far-flying parts at the target")
        s.add_argument('--leave-out', default='', metavar='S:B,...',
                       help="parts not carried (spawn index:bone), for an effect too large for one chunk")
        s.add_argument('--key', type=int, help='the species key: takes its chunk id from EFFECT_IDS')
        s.add_argument('--id', type=int, help='the effect id in the chunk header (default: 0x100 + the key\'s chunk index, else 0x17A)')
        s.add_argument('--out')
        s.add_argument('--mp4')
        s.add_argument('--title', default='')
    a = p.parse_args(argv)
    disc = X._disc(a)
    tables = X.Tables(disc)
    tech = X.model_scripts(disc, a.model)[a.slot]
    efe = open(a.efe, 'rb').read()
    scale = a.scale or (import_scale(a.species or '') if a.scale_from_species else FIELD_SCALE)
    chunk, info = convert(disc, tables, tech, scale, launch_table(native_chunk(efe, a.like)),
                          a.id if a.id is not None else 0x100 + EFFECT_IDS[a.key] if a.key is not None else 0x17A,
                          area=a.area, n_hits=len(tech.hits), full_length=not a.two_seconds, aim=a.aim,
                          half=not a.full_texture,
                          leave_out=[tuple(map(int, x.split(':'))) for x in a.leave_out.split(',') if x])
    print(json.dumps(info, default=str))
    if a.out:
        open(a.out, 'wb').write(chunk)
    if a.cmd == 'compare':
        frames, fid = compare(disc, tables, tech, chunk, a.title or a.model)
        ok, why = passes(fid)
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in fid.items() if k != 'rows'}),
              ('PASS' + (' (parts left out: ' + ', '.join(info['left_out']) + ')' if info.get('left_out') else '')
               if ok else 'FAIL: ' + '; '.join(why)))
        if a.mp4:
            X.write_mp4(frames, a.mp4, fps=60)
        if not ok:
            sys.exit(1)


if __name__ == '__main__':
    main()
