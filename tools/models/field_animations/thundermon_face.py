"""Thundermon's (species 252) eyes blink, through texture moves.

Both eyes are one painted red-and-white disc, drawn once into the face texture and mapped onto each side (the body is a
ball: no eyelid bone). While a clip plays the engine can copy a rectangle inside the model's own texture slot (texture-move
instructions, the way every original Digimon blinks), so a blink pastes a frame over the painted disc: no mesh, skeleton or
palette change.

Texture layout (pixels; the texture is 256x128, 4 bits; every face quad uses palette row 1):
  eye block      (16, 20)  32x28  the painted disc (about 26x25, with its small shadow) on the ball's blue (index 4)
  eye frames     (96, 72) open (a copy of the painted block), (128, 72) shut, (160, 72) half shut
The frame texels are ones no face of the model samples. Texture moves copy index pixels only, so every frame keeps the
palette row of the block it is drawn over.
"""

W = 256
EYE_AT, EYE_SIZE = (16, 20), (32, 28)
EYE_FRAMES = ((96, 72), (128, 72), (160, 72))          # open, shut, half shut
OPEN, SHUT, HALF = 0, 1, 2
BLUE, LASH, LASH_SOFT = 4, 9, 1                          # the ball's colour, the darkest line, the eye's dark rim
DISC_TOP, DISC_MID = 22 - EYE_AT[1], 34 - EYE_AT[1]     # the disc's first row and its middle, inside the block
DISC_X = (18 - EYE_AT[0], 43 - EYE_AT[0])


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _lid(row, x, depth):
    """Height of the lid's line at column x: a curve that bulges down in the middle."""
    mid = (DISC_X[0] + DISC_X[1]) / 2
    half = (DISC_X[1] - DISC_X[0]) / 2 + .5
    d = (x - mid) / half
    return None if abs(d) >= 1 else row + int(round(depth * (1 - d * d)))


def eye_frame(block, state):
    """The painted block as a frame: shut (the ball's blue with a curved lash) or half shut (the top of the eye covered)."""
    w, h = EYE_SIZE
    if state == SHUT:
        out = [[BLUE] * w for _ in range(h)]
        for x in range(w):
            y = _lid(DISC_MID + 1, x, 3)
            if y is not None:
                out[y][x] = out[y + 1][x] = LASH
                if _lid(DISC_MID + 1, x - 1, 3) is None or _lid(DISC_MID + 1, x + 1, 3) is None:
                    out[y][x] = out[y + 1][x] = LASH_SOFT
        return out
    out = [row[:] for row in block]
    for x in range(w):
        edge = _lid(DISC_MID - 3, x, 2)
        if edge is None:
            continue
        for y in range(DISC_TOP, edge):
            out[y][x] = BLUE
        out[edge][x] = LASH
    return out


def stamp(tim):
    """The eye frames into their spare texels (in place)."""
    block = _grab(tim, EYE_AT, EYE_SIZE)
    _put(tim, EYE_FRAMES[OPEN], block)
    _put(tim, EYE_FRAMES[SHUT], eye_frame(block, SHUT))
    _put(tim, EYE_FRAMES[HALF], eye_frame(block, HALF))
    return block


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move(EYE_FRAMES[state], EYE_SIZE, EYE_AT)


def blink(at, long=False):
    """Eye states (tick, state): half shut, shut (for a tired blink, longer, then half again), then open."""
    if long:
        return [(at, HALF), (at + 1, SHUT), (at + 4, HALF), (at + 5, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 3, OPEN)]


def events(eyes, ticks):
    """Texture-move events (tick, 'tex', move): open eyes at tick 0, then every change of the plan (tick, state), which
    must stay inside the clip, in order, and end in open eyes so that the loop closes and a clip cut in mid-blink is
    repaired by the next one."""
    assert all(0 < t < ticks for t, _ in eyes), 'eye changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'eye changes in order'
    assert not eyes or eyes[-1][1] == OPEN, 'a clip must end with open eyes'
    return [(0, 'tex', eye_move(OPEN))] + [(t, 'tex', eye_move(s)) for t, s in eyes]
