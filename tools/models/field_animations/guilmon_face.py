"""Guilmon's (species 433) blinking eyes, through texture moves.

Like Growlmon's, the head has no eyelid bone or eye piece: each eye is painted in the texture (a yellow iris with a slit
pupil, a white glint, a dark outline) and the same painted block is drawn on both sides of the face (the head's triangles at
u 80-111, v 20-31, palette row 0). A clip pastes a frame over the block with texture-move instructions (the way every
original Digimon blinks): no mesh, skeleton or palette change.

Texture layout (pixels; the texture is 256x128, 4 bits; rows 96..127 are sampled by no triangle of the model):
  eye block   (80, 20)  32x12  the painted eye (x 90-103, y 21-30) and the skin around it, which every frame keeps
  eye frames  row 96, x = 0, 32, 64: open (a copy of the painted block), half shut, shut.
Texture moves copy index pixels only, so every frame keeps the palette row of the block it is drawn over.
"""


W = 256
EYE_AT, EYE_SIZE = (80, 20), (32, 12)
EYE_FRAMES = ((0, 96), (32, 96), (64, 96))               # open, half shut, shut
OPEN, HALF, SHUT = 0, 1, 2
# palette row 0: 0-1 the darkest (outline and pupil), 2-6 the skin (dark to light), 7-12 greys, 13-15 the iris
DARK, DARK_SOFT = 0, 1
EYE_COLOURS = range(8, 16)


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _extent(block):
    """Per block column: (top, bottom) rows of the eye, the iris, white and pupil with their outline (None: no eye here)."""
    out = {}
    for x in range(EYE_SIZE[0]):
        ys = [y for y in range(EYE_SIZE[1]) if block[y][x] in EYE_COLOURS]
        if ys:
            out[x] = (min(ys), max(ys))
    return out


def eye_frame(block, state):
    """The painted block as a frame: half shut (the skin over the eye's upper part, a lid line along its edge) or shut."""
    out = [row[:] for row in block]
    ext = _extent(block)
    xs = sorted(ext)
    lo_x, hi_x = xs[0] - 1, xs[-1] + 1                    # the outline one column beyond each end
    for x in range(lo_x, hi_x + 1):
        top, bottom = ext.get(x, ext[xs[0]] if x < xs[0] else ext[xs[-1]])
        top, bottom = max(top - 1, 0), min(bottom + 1, EYE_SIZE[1] - 1)     # with the outline above and below
        above, below = block[max(top - 1, 0)][x], block[min(bottom + 1, EYE_SIZE[1] - 1)][x]
        if above in (DARK, DARK_SOFT) or above in EYE_COLOURS:
            above = 4
        if below in (DARK, DARK_SOFT) or below in EYE_COLOURS:
            below = 3
        d = (x - (lo_x + hi_x) / 2) / ((hi_x - lo_x) / 2 + .5)
        height = bottom - top
        if state == SHUT:
            lid = top + height * (0.42 + 0.3 * (1 - d * d))        # the lid line sags in the middle, two dark rows
            first, last = top, bottom
        else:
            lid = top + height * (0.30 + 0.12 * (1 - d * d))
            first, last = top, int(lid)
        for y in range(first, last + 1):
            if state == SHUT:
                mix = (y - top) / max(1, height)
                out[y][x] = above if mix < 0.5 else below
            else:
                out[y][x] = above
        edge = abs(d) > 0.82
        for k in (0,) if state == HALF else (0, 1):
            y = int(round(lid)) + k
            if first <= y <= max(last, int(round(lid)) + 1) and 0 <= y < EYE_SIZE[1]:
                out[y][x] = DARK if state == SHUT else (DARK_SOFT if edge or k else DARK)
    return out


def stamp(tim):
    """The eye frames into their spare texels (in place)."""
    block = _grab(tim, EYE_AT, EYE_SIZE)
    _put(tim, EYE_FRAMES[OPEN], block)
    _put(tim, EYE_FRAMES[HALF], eye_frame(block, HALF))
    _put(tim, EYE_FRAMES[SHUT], eye_frame(block, SHUT))


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move(EYE_FRAMES[state], EYE_SIZE, EYE_AT)


def blink(at, closed=2, heavy=False):
    """Eye states (tick, state): half shut, shut for `closed` ticks, half shut, open. A heavy (tired) blink is slower:
    two ticks to shut and a longer half shut on the way back."""
    if heavy:
        return [(at, HALF), (at + 2, SHUT), (at + 2 + closed, HALF), (at + 4 + closed, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 1 + closed, HALF), (at + 2 + closed, OPEN)]


def events(eyes, ticks, eye0=OPEN):
    """Texture-move events (tick, 'tex', move): the open eye at tick 0, then every change of the plan (tick, state), inside
    the clip, in order, ending in its first state so that the loop closes and a clip cut in the middle of a blink is
    repaired by the next one."""
    assert all(0 < t < ticks for t, _ in eyes), 'eye changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'eye changes in order'
    assert not eyes or eyes[-1][1] == eye0, 'a clip must end with its first face'
    return [(0, 'tex', eye_move(eye0))] + [(t, 'tex', eye_move(k)) for t, k in eyes]
