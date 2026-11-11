"""Garbagemon's (species 269) face: eyes that shut and a grin that opens, through texture moves.

The two eyes are one painted picture (the white of the eye, the blue iris, a black outline along its lower and right edge,
skin around it) mapped onto both sides of the head, and the grin is one strip of teeth on a plate hung under the head
(bone 19): there is no eyelid and no jaw bone to turn, so the face acts by pasting frames over those pictures. While a
clip plays the engine copies rectangles inside the model's own texture slot (texture-move instructions, the way every
original Digimon blinks): no mesh, skeleton or palette change. A move copies index pixels only, so every frame keeps the
palette row of the picture it is drawn over (row 8 for the eye, row 1 for the teeth), and uses only the colours of that row.

Texture layout (pixels; the texture is 256x128, 4 bits):
  eye picture   (148, 96)  40x32; the eye's own texels are a slanted band inside it (EYE_SPANS: the texels no other face
                samples) and the rest of the rectangle is copied unchanged
  teeth picture (220, 64)  32x16: the strip of teeth, upper teeth over a zigzag of tooth tips over the lower teeth
  frames        packed into blank texels no face samples (the top rows and a few pockets, EYE_PLACES and MOUTH_PLACES):
                a frame is stored as the rectangles that hold the texels differing between the states (EYE_BANDS, three
                rows each; MOUTH_BANDS, eight and seven rows), one texture move each. A band that two states paint with
                the same pixels is stored once. The packing leaves the 17x17 texels at the top left free: the flat sprite
                (tools/flatsprite.py) needs a 15x15 cell and the build stops with "no room for the flat sprite" without
                it. The game's own eye frames (60..107, 24..39,
                its iris-only blink, which the clips already reset at tick 0) are left as they are
A shut eye covers the white and the iris with the lid's skin and keeps the black outline as the lash; a half shut eye
has the lid down to the middle with a black edge. An open mouth slides the upper teeth up and the lower teeth down by
the same number of texels along the zigzag; the rows they uncover between them are the dark inside of the mouth.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 269
NB = 22
SOURCE = '93211a4f67ad7b89c9a15ea0a0377f3725c8e71942f8d405fc92af0101f9ad52'
SOURCE_TIM = 'd98fcb3252423bd57543206e0edbeb175fe9d7c6f4e0982859f4293338e01370'
W = 256
EYE_AT, EYE_SIZE = (148, 96), (40, 32)
MOUTH_AT, MOUTH_SIZE = (220, 64), (32, 16)
# the eye's texels (row -> first and last column): the ones the eye's own triangles cover and no other triangle does
EYE_SPANS = {
    96: (183, 186), 97: (181, 186), 98: (180, 186), 99: (178, 186), 100: (177, 186), 101: (176, 186), 102: (173, 186),
    103: (170, 186), 104: (168, 186), 105: (165, 186), 106: (163, 186), 107: (160, 186), 108: (158, 186), 109: (156, 186),
    110: (148, 186), 111: (148, 186), 112: (149, 186), 113: (149, 184), 114: (150, 183), 115: (150, 182), 116: (149, 181),
    117: (149, 179), 118: (148, 178), 119: (148, 177), 120: (148, 176), 121: (148, 173), 122: (150, 171), 123: (152, 169),
    124: (154, 167), 125: (156, 165), 126: (158, 163), 127: (160, 161)}
IRIS_BOX = (157, 105, 173, 117)                           # x0, y0, x1, y1 (exclusive): iris and pupil, inside the eye
# palette row 8 (the eye): pupil and outline, the iris's blues, skin from the outline's shadow to its light
BLACK, DARK = 1, 10
SKIN = (6, 7, 8, 9)
# palette row 1 (the teeth)
TOOTH_LINE, INSIDE, INSIDE_EDGE = 9, 1, 8
OPEN, HALF, SHUT = 0, 1, 2                                # the eye's states
REST, AJAR, WIDE = 0, 1, 2                                # the mouth's: as painted, half open, wide open
SLIDE = {REST: 0, AJAR: 2, WIDE: 4}                       # texels each row of teeth moves away from the other


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _is_rim(x, y, v):
    ix0, iy0, ix1, iy1 = IRIS_BOX
    return v in (BLACK, DARK) and not (ix0 <= x < ix1 and iy0 <= y < iy1)


def _is_ball(x, y, v):
    """A texel of the eyeball: not skin, not the outline, not clear."""
    return v >= 1 and v not in SKIN and not _is_rim(x, y, v)


def eye_frame(block, state):
    """The painted block as a frame: itself (open), the lid down to the middle with a black edge (half shut) or the whole
    ball covered with the lid's skin (shut). Only texels of EYE_SPANS change."""
    ox, oy = EYE_AT
    out = [row[:] for row in block]
    if state == OPEN:
        return out
    # the rows of the ball in each column
    cols = {}
    rim = []
    for y, (a, b) in EYE_SPANS.items():
        for x in range(a, b + 1):
            v = block[y - oy][x - ox]
            if _is_ball(x, y, v):
                cols.setdefault(x, []).append(y)
            elif _is_rim(x, y, v):
                rim.append((x, y))

    def shade(x, y):
        d = min(((x - rx) ** 2 + (y - ry) ** 2) ** .5 for rx, ry in rim)
        return SKIN[0] if d <= 1.5 else SKIN[1] if d <= 3.5 else SKIN[2] if d <= 8 else SKIN[3]
    for x, ys in cols.items():
        lo, hi = min(ys), max(ys)
        edge = hi + 1 if state == SHUT else lo + (hi - lo + 1) // 2
        for y in ys:
            if y < edge:
                out[y - oy][x - ox] = shade(x, y)
        if state == HALF:
            for y in (edge, edge + 1):
                if y in ys:
                    out[y - oy][x - ox] = BLACK
        else:                                              # the lash: the outline thickened by a row
            out[hi - oy][x - ox] = BLACK
    return out


def _cut(rest):
    """For each column of the teeth, the last row of the upper teeth (the zigzag's own row)."""
    h = len(rest)
    cut = []
    for x in range(len(rest[0])):
        rows = [y for y in range(h // 2 - 3, h // 2 + 3) if rest[y][x] == TOOTH_LINE]
        cut.append(max(rows) if rows else None)
    known = [(x, c) for x, c in enumerate(cut) if c is not None]
    for x, c in enumerate(cut):
        if c is None:
            left = [k for k in known if k[0] < x]
            right = [k for k in known if k[0] > x]
            cut[x] = round(sum(k[1] for k in ([left[-1]] if left else []) + ([right[0]] if right else [])) /
                           (bool(left) + bool(right)))
    return cut


def mouth_frame(rest, state):
    """The teeth with the upper row slid up and the lower row slid down by SLIDE[state] texels along the zigzag."""
    s = SLIDE[state]
    h, w = len(rest), len(rest[0])
    cut = _cut(rest)
    out = [row[:] for row in rest]
    if not s:
        return out
    for x in range(w):
        c = cut[x]
        if rest[c][x] == 0:                                # the rectangle's clear columns stay as they are
            continue
        col = [INSIDE_EDGE if y in (c - s + 1, c + s) else INSIDE for y in range(h)]
        for y in range(h):
            if y + s <= c:                                 # the upper teeth, moved up
                col[y] = rest[y + s][x]
            elif y - s > c:                                # the lower teeth, moved down
                col[y] = rest[y - s][x]
        # the bottom row of the strip is the clear row the importer left below the teeth: keep it
        for y in range(h):
            out[y][x] = col[y]
        out[h - 1][x] = rest[h - 1][x]
    return out


# where each state's bands sit: EYE_PLACES[state][band] = (x, y) in pixels (x a multiple of 4)
EYE_BANDS = [(168, 102, 16, 3), (160, 105, 24, 3), (148, 108, 36, 3), (148, 111, 36, 3), (152, 114, 28, 3), (160, 117, 16, 3)]
MOUTH_BANDS = [(220, 64, 32, 8), (220, 72, 32, 7)]      # (the picture's last row never changes)
EYE_PLACES = [[(80, 8), (220, 0), (184, 0), (136, 9), (20, 10), (80, 11)],
              [(112, 8), (228, 10), (148, 0), (176, 6), (148, 6), (80, 11)],
              [(112, 8), (228, 10), (140, 12), (148, 3), (184, 3), (20, 7)]]
MOUTH_PLACES = [[(84, 0), (52, 0)], [(116, 0), (20, 0)], [(48, 7), (212, 3)]]


def _band_rows(rows, origin, band):
    x, y, w, h = band
    return [rows[y - origin[1] + j][x - origin[0]:x - origin[0] + w] for j in range(h)]


def stamp(tim):
    """The eye and mouth frames into their spare texels (in place); returns the painted blocks."""
    eye = _grab(tim, EYE_AT, EYE_SIZE)
    mouth = _grab(tim, MOUTH_AT, MOUTH_SIZE)
    for state in (OPEN, HALF, SHUT):
        rows = eye_frame(eye, state)
        for band, at in zip(EYE_BANDS, EYE_PLACES[state]):
            _put(tim, at, _band_rows(rows, EYE_AT, band))
    for state in (REST, AJAR, WIDE):
        rows = mouth_frame(mouth, state)
        for band, at in zip(MOUTH_BANDS, MOUTH_PLACES[state]):
            _put(tim, at, _band_rows(rows, MOUTH_AT, band))
    return eye, mouth


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_moves(state):
    return [_move(at, band[2:], band[:2]) for band, at in zip(EYE_BANDS, EYE_PLACES[state])]


def mouth_moves(state):
    return [_move(at, band[2:], band[:2]) for band, at in zip(MOUTH_BANDS, MOUTH_PLACES[state])]


def blink(at, long=False):
    """Eye states (tick, state): half shut, shut, half again, open: three ticks of a blink (a tired one lasts five)."""
    if long:
        return [(at, HALF), (at + 1, SHUT), (at + 4, HALF), (at + 5, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 2, HALF), (at + 3, OPEN)]


def events(eyes, mouth, ticks):
    """Texture-move events (tick, 'tex', move): eyes open and mouth shut at tick 0, then every change of the plans
    (tick, state), which must stay inside the clip, in order, and end at rest, so that the loop closes and a clip cut in
    mid-change is repaired by the next one."""
    for plan, rest in ((eyes, OPEN), (mouth, REST)):
        assert all(0 < t < ticks for t, _ in plan), 'changes inside the clip'
        assert [t for t, _ in plan] == sorted(t for t, _ in plan), 'changes in order'
        assert not plan or plan[-1][1] == rest, 'a clip must end at rest'
    out = {}
    for t, s in [(0, OPEN)] + list(eyes):
        out.setdefault(t, []).extend(eye_moves(s))
    for t, s in [(0, REST)] + list(mouth):
        out.setdefault(t, []).extend(mouth_moves(s))
    return [(t, 'tex', m) for t in sorted(out) for m in out[t]]


# ------------------------------------------------------------------ the plans (tick, state); the engine runs 20 ticks a second
IDLE_REPEATS = 7                       # the standing loop is 19 ticks: seven of them make 133 ticks, room for the face
PLANS = {
    # idle (slots 0, 1, 18, 33): a blink, a slow yawn, a double blink, a small gulp
    0: dict(eyes=blink(30) + blink(98) + blink(105),
            mouth=[(52, AJAR), (54, WIDE), (72, AJAR), (74, REST), (118, AJAR), (127, REST)]),
    # walk: the mouth opens as the body rises and snaps shut on the footfall (tick 7)
    2: dict(eyes=blink(11), mouth=[(2, AJAR), (4, WIDE), (7, REST)]),
    # tired walk: a slow heavy blink and a slow gape after the footfall (tick 5)
    3: dict(eyes=blink(1, long=True), mouth=[(9, AJAR), (11, WIDE), (17, AJAR), (19, REST)]),
    # run: two quick snaps of the jaws, one on each footfall rhythm, and a blink between
    4: dict(eyes=blink(11), mouth=[(3, WIDE), (7, REST), (15, WIDE), (18, REST)]),
}


def unroll(animation, repeats):
    """The same program played `repeats` loops long: the keys of the first loop copied with their frames shifted (the
    texture move of its first frame, the game's iris reset, is not repeated)."""
    result = copy.deepcopy(animation)
    period = animation.frame_count - 1
    head = [i for i in animation.instrs if i['op'] == 'loop_start']
    inner = [i for i in animation.instrs if i['op'] not in ('loop_start', 'loop_end', 'end')]
    body = list(inner)
    for k in range(1, repeats):
        for i in inner:
            if i['op'] == 'tex':                 # the game's own iris reset belongs to the first loop only
                continue
            c = copy.deepcopy(i)
            c['frame'] += k * period
            body.append(c)
    loop_end = next(i for i in animation.instrs if i['op'] == 'loop_end')
    tail = dict(loop_end, frame=animation.frame_count + (repeats - 1) * period)
    result.instrs = head + body + [tail, dict(op='end')]
    result.frame_count = tail['frame']
    return result


def add_events(animation, evs):
    """Texture moves inserted after the first key of their frame (tick t is frame t + 1); everything else untouched."""
    result = copy.deepcopy(animation)
    instrs = result.instrs
    for t, _, move in evs:
        frame = t + 1
        at = next(n for n, i in enumerate(instrs) if i['op'] == 'key' and i['frame'] == frame)
        end = at + 1
        while end < len(instrs) and instrs[end]['op'] in ('tex', 'sound') and instrs[end]['frame'] == frame:
            end += 1
        instrs.insert(end, dict(op='tex', frame=frame, **copy.deepcopy(move)))
    return result


def ticks_of(animation):
    return animation.frame_count - 1


def decoded(animation, ticks):
    p = mmd.AnimPlayer(animation, NB)
    out = []
    for _ in range(ticks):
        p.tick(stop_at_infinite_loop=False)
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(p.root)
        out.append(snap)
    return out


def parse(data):
    return mmd.MMD.parse(data, NB)


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Garbagemon face requires the model as `edit.py get 269` gave it before this change')
    model = parse(data)
    result = copy.deepcopy(model)
    checks = []
    for slot, plan in PLANS.items():
        index = model.anims.table[slot]
        old = model.anims.anims[index]
        base = unroll(old, IDLE_REPEATS) if slot == 0 else old
        ticks = ticks_of(base)
        program = add_events(base, events(plan['eyes'], plan['mouth'], ticks))
        program.tail = b''
        result.anims.anims[index] = program
        checks.append(dict(slot=slot, ticks=ticks, tex_moves=sum(i['op'] == 'tex' for i in program.instrs),
                           shared_by=[s for s, v in enumerate(model.anims.table) if v == index]))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = parse(output)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective), checks=checks,
                        storage=motionstorage.require(output, NB))


def texture(tim):
    """The texture before this change -> the same with the eye and mouth frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('the texture is not the import as `edit.py get 269` gave it before this change')
    result = mmd.Tim4(tim)
    stamp(result)
    return result.to_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'build/imported-model-edit/edit/269-Garbagemon.MMD')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--tim', type=Path, default=ROOT / 'build/imported-model-edit/edit/269-Garbagemon.TIM')
    p.add_argument('--tim-out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    data, proof = build(a.source.read_bytes())
    a.out.write_bytes(data)
    a.tim_out.write_bytes(texture(a.tim.read_bytes()))
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ('changed_slots', 'checks')}), proof['storage']['resident_bytes'], len(data))


if __name__ == '__main__':
    main()
