"""Divermon's (species 304) face: blinking eyes and a mouth that opens and shuts, through texture moves.

The head has no eyelid or jaw bone. One painted eye (a green iris in a pale-blue rim, on transparent texels) is drawn on
both sides of the face over the head's own pale skin, and the grin is a strip of teeth between two pink lips. While a clip
plays the engine can copy a rectangle inside the model's own texture slot (texture-move instructions, the way every
original Digimon blinks), so the face acts by pasting a frame over the eye or the teeth: no mesh, skeleton or palette
change.

Texture layout (pixels; the texture is 256x128, 4 bits; its rows 0..21 are sampled by no face):
  eye block    (224, 110)  24x18  the painted eye (x 227-245, y 112-127) and, in its last two columns, the neighbour's
                                  texels (copied unchanged into every frame). Face palette row 3, where index 15 is
                                  transparent: the pale skin of the head shows through it.
  eye frames   row 0, x = 0, 24, 48: open (a copy of the painted block), half shut, shut. A shut eye is the skin with a
                                  curved lash; a half-shut one has the skin over its upper part and a lash along the lid.
  teeth block  (76, 25)    16x7   the strip of teeth in the grin (x 78-90 of it change; palette row 5)
  mouth frames row 0, x = 72, 88, 104, 120, 136: the grin as painted (a copy), lips shut (pink with a dark seam), ajar
                                  (the teeth shown above and below a dark gap), open (dark inside and a tongue) and wide
                                  (a bigger dark mouth with a tongue).
Texture moves copy index pixels only, so every frame keeps the palette row of the block it is drawn over.
"""

W = 256
EYE_AT, EYE_SIZE = (224, 110), (24, 18)
EYE_FRAMES = ((0, 0), (24, 0), (48, 0))                  # open, half shut, shut
OPEN, HALF, SHUT = 0, 1, 2
CLEAR, LASH, LASH_SOFT = 15, 0, 1                        # transparent, the darkest line and its soft end (palette row 3)
EYE_X = (227, 245)                                       # the painted eye's columns (the next two are a neighbour's)
EYE_MID = 236.0                                          # its centre column
LID_ROW = 121                                            # where a shut lid's line lies at the middle

MOUTH_AT, MOUTH_SIZE = (76, 25), (16, 7)
MOUTH_FRAMES = ((72, 0), (88, 0), (104, 0), (120, 0), (136, 0))
REST, MSHUT, AJAR, MOPEN, WIDE = 0, 1, 2, 3, 4
TEETH_X = (2, 15)                                        # the columns of the block that carry the teeth (78..90)
# palette row 5: 0-4 the pinks (light to deep), 5 a dark rose, 6-15 greys from nearly black to light
PINK_LIP, PINK_MID, PINK_DEEP, SEAM, DARK, DARK_SOFT = 1, 2, 3, 5, 6, 7


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _lid(x, row, depth):
    """Row of a lid's line at column x: a curve that bulges down in the middle (None outside the eye)."""
    half = (EYE_X[1] - EYE_X[0]) / 2 + .5
    d = (x - EYE_MID) / half
    return None if abs(d) >= 1 else row + int(round(depth * (1 - d * d)))


def eye_frame(block, state):
    """The painted block as a frame: half shut (the skin over the eye's upper part, a lash along the lid) or shut (only
    the skin and a curved lash)."""
    out = [row[:] for row in block]
    for dx in range(EYE_X[0] - EYE_AT[0], EYE_X[1] - EYE_AT[0] + 1):
        x = EYE_AT[0] + dx
        edge = _lid(x, LID_ROW - 4, 2) if state == HALF else None
        for dy in range(EYE_SIZE[1]):
            if state == SHUT or (edge is not None and EYE_AT[1] + dy < edge):
                out[dy][dx] = CLEAR
    for x in range(EYE_X[0], EYE_X[1] + 1):
        y = _lid(x, LID_ROW - 4 if state == HALF else LID_ROW, 2 if state == HALF else 3)
        if y is None:
            continue
        end = _lid(x - 1, 0, 1) is None or _lid(x + 1, 0, 1) is None
        for k in ((0,) if state == HALF else (0, 1)):
            out[y - EYE_AT[1] + k][x - EYE_AT[0]] = LASH_SOFT if end else LASH
    return out


def mouth_frame(block, state):
    """The teeth block as a frame. Two quads draw the strip, one on each side of the middle: column 78 lands at the
    middle of the mouth, column 90 at its corners, and rows 0-5 (y 25-30) from the upper lip down to the lower one."""
    out = [row[:] for row in block]
    if state == REST:
        return out
    lo, hi = TEETH_X
    for x in range(lo, hi):
        mid = x - lo <= 5                      # the tongue lies in the middle of the mouth
        for y in range(6):
            if state == MSHUT:                 # lips together: pink with a dark seam
                v = (PINK_LIP, PINK_MID, PINK_MID, SEAM, PINK_DEEP, PINK_DEEP)[y]
            elif state == AJAR:                # the teeth above and below a thin dark gap
                v = (DARK if x - lo < 11 else DARK_SOFT) if y in (2, 3) else block[y][x]
            elif state == MOPEN:               # the top teeth, dark inside, the tongue at the bottom
                v = block[y][x] if y == 0 else DARK if y <= 3 else (PINK_MID if y == 4 else PINK_DEEP) if mid else DARK_SOFT
            else:                              # wide: dark almost to the top, a bigger tongue
                v = DARK if y <= 2 else (PINK_MID if y == 3 else PINK_DEEP) if mid else DARK_SOFT
            out[y][x] = v
    return out


def stamp(tim):
    """The eye and mouth frames into their spare texels (in place)."""
    block = _grab(tim, EYE_AT, EYE_SIZE)
    _put(tim, EYE_FRAMES[OPEN], block)
    _put(tim, EYE_FRAMES[HALF], eye_frame(block, HALF))
    _put(tim, EYE_FRAMES[SHUT], eye_frame(block, SHUT))
    teeth = _grab(tim, MOUTH_AT, MOUTH_SIZE)
    for state, at in enumerate(MOUTH_FRAMES):
        _put(tim, at, mouth_frame(teeth, state))


# ------------------------------------------------------------------ what the clips do
def _move(src, size, dst):
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move(EYE_FRAMES[state], EYE_SIZE, EYE_AT)


def mouth_move(state):
    return _move(MOUTH_FRAMES[state], MOUTH_SIZE, MOUTH_AT)


def blink(at, slow=False):
    """Eye states (tick, state): half shut, shut, half shut, open; a slow (tired) blink stays shut longer."""
    if slow:
        return [(at, HALF), (at + 1, SHUT), (at + 5, HALF), (at + 7, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 3, HALF), (at + 4, OPEN)]


def events(eyes, mouth, ticks, eye0=OPEN, mouth0=REST):
    """Texture-move events (tick, 'tex', move): the first face at tick 0, then every change of the plans (tick, state),
    inside the clip, in order, and each ending in its first state so that the loop closes and a clip cut in the middle
    of a blink is repaired by the next one."""
    for plan, first in ((eyes, eye0), (mouth, mouth0)):
        assert all(0 < t < ticks for t, _ in plan), 'face changes inside the clip'
        assert [t for t, _ in plan] == sorted(t for t, _ in plan), 'face changes in order'
        assert not plan or plan[-1][1] == first, 'a clip must end with its first face'
    out = [(0, 'tex', eye_move(eye0)), (0, 'tex', mouth_move(mouth0))]
    out += [(t, 'tex', eye_move(k)) for t, k in eyes] + [(t, 'tex', mouth_move(k)) for t, k in mouth]
    out.sort(key=lambda e: e[0])
    return out
