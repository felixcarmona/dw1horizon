"""Solarmon's (species 251) eyes blink, through texture moves.

The sun has no eyelid bone: its two eyes are one painted disc mapped onto both. While a clip plays the engine can copy a
rectangle inside the model's own texture slot (texture-move instructions, the way every original Digimon blinks), so the
blink pastes a frame over the painted disc: no mesh, skeleton or palette change. The mouth is left as painted.

Texture layout (pixels; the texture is 256x128, 4 bits):
  eye disc       (36, 52)   24x24  drawn on both eyes (palette row 4)
  eye frames     (200, 72)  open (a copy of the painted disc), (200, 96) shut, (200, 120) 24x8 half shut (only the
                 top eight rows of the disc: the first step of a blink)
The frame texels are ones no face of the model samples. Texture moves copy index pixels only, so every frame keeps the
palette row of the disc it is drawn over.
"""

W = 256
EYE_AT, EYE_SIZE = (36, 52), (24, 24)
EYE_FRAMES = ((200, 72), (200, 96), (200, 120))       # open, shut, half (the top rows only)
HALF_ROWS = 8
OPEN, SHUT, HALF = 0, 1, 2
EYE_SKIN, EYE_LASH = 15, 14                           # row 4: the skin round the eye and the darkest line


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def eye_frame(disc, state):
    """The 24x24 painted disc as a frame: shut (skin with a curved lash line) or half shut (24x8, top rows)."""
    out = [row[:] for row in disc]
    w, h = EYE_SIZE
    mid, half_w = (w - 1) / 2, w / 2
    if state == SHUT:
        out = [[EYE_SKIN] * w for _ in range(h)]
        for x in range(w):
            d = (x - mid) / half_w
            if abs(d) < 1:
                y = 11 + int(round(3 * (1 - d * d)))
                out[y][x] = out[y + 1][x] = EYE_LASH
        return out
    out = out[:HALF_ROWS]
    for x in range(w):
        d = (x - mid) / half_w
        edge = HALF_ROWS - 1 - int(round(2 * (1 - d * d)))
        for y in range(HALF_ROWS):
            if disc[y][x] != EYE_SKIN or y == edge:
                if y < edge:
                    out[y][x] = EYE_SKIN
                elif y == edge:
                    out[y][x] = EYE_LASH
    return out


def stamp(tim):
    """The eye frames into their spare texels (in place)."""
    disc = _grab(tim, EYE_AT, EYE_SIZE)
    _put(tim, EYE_FRAMES[OPEN], disc)
    _put(tim, EYE_FRAMES[SHUT], eye_frame(disc, SHUT))
    _put(tim, EYE_FRAMES[HALF], eye_frame(disc, HALF))
    return disc


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    size = (EYE_SIZE[0], HALF_ROWS) if state == HALF else EYE_SIZE
    return _move(EYE_FRAMES[state], size, EYE_AT)


def blink(at):
    """Eye states (tick, state): half shut, shut for two ticks, then open."""
    return [(at, HALF), (at + 1, SHUT), (at + 3, OPEN)]


def events(eyes, ticks):
    """Texture-move events (tick, 'tex', move): open eyes at tick 0, then every change of the plan (tick, state), which
    must stay inside the clip, in order, and end in open eyes so that the loop closes and a clip cut in mid-blink is
    repaired by the next one."""
    assert all(0 < t < ticks for t, _ in eyes), 'eye changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'eye changes in order'
    assert not eyes or eyes[-1][1] == OPEN, 'a clip must end with open eyes'
    return [(0, 'tex', eye_move(OPEN))] + [(t, 'tex', eye_move(s)) for t, s in eyes]
