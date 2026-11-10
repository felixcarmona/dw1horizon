"""Gomamon's (species 217) blink and open mouth: texture frames in the free rows of its texture, and the schedule that
copies them over the painted eye and mouth.

The head has no eyelid, jaw or mouth bone: the eyes and the mouth are two sprites painted on its texture. The engine
copies rectangles inside the model's own texture slot while a clip plays (texture-move instructions, the way every
original Digimon blinks), so the face acts by pasting a new frame over the sprite: no mesh, skeleton or palette change.

Texture layout (pixels, texture is 256x128; the used part, rows 0..79, is unchanged):
  eye sprite   (52, 8)  44x40   painted on both eyes (palette row 3)
  mouth sprite (0, 0)   48x48                       (palette row 2)
  frames       row 80 down, in the free rows: eye open (a backup of the sprite), eye half shut, eye shut,
               mouth closed (a backup), mouth open; x = 0, 44, 88, 132, 180.
Texture moves copy index pixels only, so every frame uses the palette row of the sprite it replaces.
"""
import math

EYE_AT, EYE_SIZE = (52, 8), (44, 40)
MOUTH_AT, MOUTH_SIZE = (0, 0), (48, 48)
FRAME_Y = 80
EYE_FRAMES = (0, 44, 88)          # open, half, shut
MOUTH_FRAMES = (132, 180)         # closed, open
W = 256
SKIN = 10                         # the fur's white in the eye's palette row
OUTLINE, DARK = 0, 8              # the eye's black and its dark grey
MOUTH_DARK = 15                   # the mouth line's darkest index
CHEEK = 14                        # the crest's purple that overlaps the eye's corner (never painted over)


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _inside(px):
    """The pixels enclosed by the eye's dark outline (the outline itself included)."""
    h, w = len(px), len(px[0])
    dark = {0, 3, 8, 15}
    outside, todo = set(), [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while todo:
        x, y = todo.pop()
        if (x, y) in outside or not (0 <= x < w and 0 <= y < h) or px[y][x] in dark:
            continue
        outside.add((x, y))
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return [[(x, y) not in outside for x in range(w)] for y in range(h)]


def _grow(mask, r):
    h, w = len(mask), len(mask[0])
    out = [row[:] for row in mask]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r + 1 and 0 <= x + dx < w and 0 <= y + dy < h:
                            out[y + dy][x + dx] = True
    return out


def _stroke(px, curve, thick):
    for x, y in curve:
        for dy in range(-thick, thick + 1):
            yy = int(round(y)) + dy
            if 0 <= yy < len(px) and 0 <= x < len(px[0]):
                px[yy][x] = OUTLINE if abs(dy) < thick else DARK


def _arc(x0, x1, y, sag):
    mid, half = (x0 + x1) / 2, (x1 - x0) / 2
    return [(x, y + sag * (1 - ((x - mid) / half) ** 2)) for x in range(x0, x1 + 1)]


def eye_frames(open_eye):
    """(half shut, shut): the eyelid drawn over the open sprite, then the whole eye wiped to a closed line."""
    ins = _inside(open_eye)
    cover = _grow(ins, 2)
    cols = [x for row in ins for x, v in enumerate(row) if v]
    rows = [y for y, row in enumerate(ins) if any(row)]
    x0, x1, y0, y1 = min(cols), max(cols), min(rows), max(rows)
    mid = (y0 + y1) / 2
    half = [r[:] for r in open_eye]
    lid = _arc(x0, x1, mid - 4, 5)
    top = {x: y for x, y in lid}
    for y, row in enumerate(half):
        for x in range(len(row)):
            if cover[y][x] and row[x] != CHEEK and x in top and y < top[x]:
                row[x] = SKIN
    _stroke(half, lid, 2)
    shut = [r[:] for r in open_eye]
    for y, row in enumerate(shut):
        for x in range(len(row)):
            if cover[y][x] and row[x] != CHEEK:
                row[x] = SKIN
    _stroke(shut, _arc(x0 + 2, x1 - 1, mid + 2, 5), 2)
    return half, shut


def mouth_open(closed, depth=10, span=36):
    """The mouth with its jaw dropped: below the dark line, every column slides down by a smooth bump of up to `depth`
    pixels and the gap fills with the line's darkest index. The fangs on the right (x >= span) stay."""
    h, w = len(closed), len(closed[0])
    lum = {2: 0xEF, 8: 0x5A, 3: 0x73, 15: 0x31}
    out = [r[:] for r in closed]
    for x in range(min(span, w)):
        band = [y for y in range(h) if closed[y][x] in (8, 3, 15)]
        if not band:
            continue
        y_mid = (min(band) + max(band)) // 2
        d = int(round(depth * math.sin(math.pi * (x + 1) / (span + 1)) ** 0.8))
        if d <= 0:
            continue
        for y in range(h - 1, y_mid + d, -1):
            out[y][x] = closed[y - d][x]
        for y in range(y_mid + 1, min(h, y_mid + d + 1)):
            out[y][x] = MOUTH_DARK
        if y_mid + d + 1 < h:
            out[y_mid + d][x] = 8 if d > 1 else out[y_mid + d][x]
    return out


def stamp(tim):
    """Paste the five frames into the free rows (in place); the texture's other texels do not change."""
    eye = _grab(tim, EYE_AT, EYE_SIZE)
    mouth = _grab(tim, MOUTH_AT, MOUTH_SIZE)
    assert not any(tim.idx[FRAME_Y * W:]), 'rows 80 down of the texture must be free'
    half, shut = eye_frames(eye)
    for x, frame in zip(EYE_FRAMES, (eye, half, shut)):
        _put(tim, (x, FRAME_Y), frame)
    for x, frame in zip(MOUTH_FRAMES, (mouth, mouth_open(mouth))):
        _put(tim, (x, FRAME_Y), frame)


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move((EYE_FRAMES[state], FRAME_Y), EYE_SIZE, EYE_AT)


def mouth_move(state):
    return _move((MOUTH_FRAMES[state], FRAME_Y), MOUTH_SIZE, MOUTH_AT)


def blink(at, slow=False):
    """Eye states (tick, 0 open | 1 half | 2 shut): half, shut, shut, half, open; slow = a tired, heavier blink."""
    if slow:
        return [(at, 1), (at + 1, 2), (at + 4, 1), (at + 6, 0)]
    return [(at, 1), (at + 1, 2), (at + 3, 1), (at + 4, 0)]


# per slot: eye states and mouth states (tick, state); the clip starts open-eyed and closed-mouthed and ends so
SCHEDULE = {
    0: dict(eyes=blink(4) + blink(12) + [(32, 1), (36, 2), (52, 2), (54, 1), (57, 0)],       # a double blink, a yawn
            mouth=[(34, 1), (54, 0)]),
    2: dict(eyes=blink(26), mouth=[]),
    3: dict(eyes=blink(30, slow=True), mouth=[(5, 1), (14, 0), (26, 1), (35, 0)]),             # tired, panting
    4: dict(eyes=blink(18), mouth=[(2, 1), (8, 0), (18, 1), (24, 0)]),                         # a pant at each bound
}


def events(slot):
    """Texture-move events (sample, 'tex', move) for a slot: the open eyes and closed mouth first, then the plan."""
    plan = SCHEDULE[slot]
    out = [(0, 'tex', eye_move(0)), (0, 'tex', mouth_move(0))]
    out += [(t, 'tex', eye_move(k)) for t, k in plan['eyes']]
    out += [(t, 'tex', mouth_move(k)) for t, k in plan['mouth']]
    return sorted(out, key=lambda e: e[0])
