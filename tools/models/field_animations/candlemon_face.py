"""Candlemon's (species 235) face: blinking eyes and a mouth that opens and shuts, through texture moves.

The candle has no eyelid or jaw bone: its two red eyes (one sprite, mirrored) and its toothy mouth are painted on the
body's texture. The engine copies rectangles inside the model's own texture slot while a clip plays (texture-move
instructions, the way every original Digimon blinks), so the face acts by pasting a frame over a sprite: no mesh,
skeleton or palette change.

Texture layout (pixels; the texture is 256x128):
  eye sprite    (8, 0)   32x24  drawn on both eyes (palette row 0)
  eye frames    (160, 32) open, (192, 32) half shut, (224, 32) shut: the source game's own blink frames, which no face
                samples (the import kept them but dropped the moves that used them)
  mouth sprite  (52, 0)  32x24  the middle of the mouth (palette row 1); its corners (x 48-51 and 84-87) never change
  mouth frames  row 56, x = 0, 32, 64, 128: the mouth as painted (a backup), half shut, shut, wide open. They replace
                four spare drawings of a hand that no face samples (x 96 keeps a spare open eye, unused too).
The mouth frames are made from the painted mouth itself: in each column the upper lip with its fangs slides down (or
up, for the wide mouth) over the dark inside and the tongue, the lower teeth stay; the slide is the same over most of
the mouth and fades to nothing at the corners, so the lip closes in a soft curve. The texels it uncovers at the top take
the wax colour of their own column. Texture moves copy index pixels only, so every frame keeps the palette row it is
drawn with.
"""

W = 256
EYE_AT, EYE_SIZE = (8, 0), (32, 24)
EYE_FRAMES = ((160, 32), (192, 32), (224, 32))        # open, half, shut
OPEN, HALF, SHUT = 0, 1, 2

MOUTH_AT, MOUTH_SIZE = (52, 0), (32, 24)
MOUTH_Y = 56
MOUTH_FRAMES = ((0, MOUTH_Y), (32, MOUTH_Y), (64, MOUTH_Y), (128, MOUTH_Y))   # rest, half, shut, wide
REST, MHALF, MSHUT, WIDE = 0, 1, 2, 3
SLIDE = {REST: 0, MHALF: 3, MSHUT: 7, WIDE: -3}       # how far the upper lip moves at the middle of the mouth (texels)
UPPER, LOWER = 12, 18                                 # rows 0..11 lip and fangs, 12..17 inside and tongue, 18..23 teeth
MIDDLE, HALF_WIDTH = 67.5, 15.5                       # the mouth's middle column and the half width that moves


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _column(col, s):
    """One column of the mouth with its upper lip slid down by s texels (up when s < 0)."""
    h = len(col)
    out = []
    for y in range(h):
        if y >= max(LOWER, UPPER + s):
            src = y                                   # the lower teeth stay
        elif y < UPPER + s:
            src = y - s                               # the lip and its fangs, slid
            if src < 0:
                out.append(col[0])                    # the wax above the lip
                continue
        else:                                         # the inside, squeezed or stretched between lip and teeth
            span = LOWER - (UPPER + s)
            src = UPPER + int((y - (UPPER + s)) * (LOWER - UPPER) / span)
        out.append(col[min(src, h - 1)])
    return out


def mouth_frame(rest, slide):
    w, h = len(rest[0]), len(rest)
    cols = []
    for x in range(w):
        d = (MOUTH_AT[0] + x + .5 - MIDDLE) / HALF_WIDTH
        k = max(0., 1 - d ** 4)
        cols.append(_column([rest[y][x] for y in range(h)], int(round(slide * k))))
    return [[cols[x][y] for x in range(w)] for y in range(h)]


def stamp(tim):
    """The mouth frames into row 56 (in place). Checks that the eye frames are the source game's blink."""
    eye = _grab(tim, EYE_AT, EYE_SIZE)
    assert _grab(tim, EYE_FRAMES[OPEN], EYE_SIZE) == eye, 'the open-eye frame must be the painted eye'
    rest = _grab(tim, MOUTH_AT, MOUTH_SIZE)
    for k, at in enumerate(MOUTH_FRAMES):
        _put(tim, at, mouth_frame(rest, SLIDE[k]))


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move(EYE_FRAMES[state], EYE_SIZE, EYE_AT)


def mouth_move(state):
    return _move(MOUTH_FRAMES[state], MOUTH_SIZE, MOUTH_AT)


def blink(at, slow=False, rest=OPEN):
    """Eye states (tick, state): half, shut, half, back to `rest`; slow = a heavier, tired blink."""
    if slow:
        return [(at, HALF), (at + 1, SHUT), (at + 4, SHUT), (at + 5, HALF), (at + 7, rest)] if rest != HALF else \
            [(at, SHUT), (at + 4, HALF)]
    return [(at, HALF), (at + 1, SHUT), (at + 2, HALF), (at + 3, rest)]


def events(eyes, mouth, ticks, eye0=OPEN, mouth0=REST):
    """Texture-move events (tick, 'tex', move): the clip's first face at tick 0, then every change of the plans (which
    must end in that first face before the last tick, so the loop closes)."""
    for plan, first in ((eyes, eye0), (mouth, mouth0)):
        assert all(0 < t < ticks for t, _ in plan), 'face changes inside the clip'
        assert [t for t, _ in plan] == sorted(t for t, _ in plan), 'face changes in order'
        assert not plan or plan[-1][1] == first, 'a clip must end with its first face'
    out = [(0, 'tex', eye_move(eye0)), (0, 'tex', mouth_move(mouth0))]
    out += [(t, 'tex', eye_move(k)) for t, k in eyes] + [(t, 'tex', mouth_move(k)) for t, k in mouth]
    out.sort(key=lambda e: e[0])
    return out
