"""MarineAngemon's (species 248) eyes: blinks and heavy lids through texture moves.

The fairy has no eyelid bone: both green eyes are one painted plate on the head's texture (the head's faces wrap it around
both eyes). While a clip plays the engine can copy a rectangle inside the model's own texture slot (texture-move
instructions, the way every original Digimon blinks), so the eye acts by pasting a frame over that plate: no mesh,
skeleton or palette change.

The plate is 36x34 texels at (8, 44): the eyeball, its dark outline and the shaded skin ring around it. Three frames live in
texels that no face of the model samples (the importer left them over):
  open  (96, 68)    a copy of the painted plate (a clip's first face, and the way back from the others)
  half  (212, 56)   the lid down over the top of the eyeball: skin above a dark lash line
  shut  (212, 92)   the eyeball covered by skin with a curved lash line
Each frame is made from the painted plate: every texel of the eyeball, its outline and its shadow ring is repainted in the
skin colour of its own row (the nearest skin texel to the left and to the right of the eye), then the lash line is drawn.
Texture moves copy index pixels only, so every frame keeps the palette row it is drawn with.
"""

W = 256
PLATE_AT, PLATE_SIZE = (8, 44), (36, 34)
FRAMES = ((96, 68), (212, 56), (212, 92))             # open, half, shut
OPEN, HALF, SHUT = 0, 1, 2

LASH = 0                                              # palette index: the darkest line of the outline
EYE_INDEX = {0, 8, 9, 10, 11, 12, 13, 14, 15}          # the outline's black, its anti-alias and the eyeball itself
RING_INDEX = {1, 2}                                   # the shaded skin ring around the outline
EYE_X = 26.0                                          # the eyeball's middle and half width
EYE_A = 15.0
LID_Y = 57                                            # y of the half lid's edge at the middle of the eyeball
SHUT_Y, SHUT_SAG = 62, 3                              # the shut lash line: its y at the ends and how far it sags


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _skin_rows(plate):
    """The plate with the eye removed: every eye/ring texel takes the skin of its column, from the nearest texel above
    (upper half of the eye) or below it (the skin there shades left to right, not top to bottom)."""
    out = [row[:] for row in plate]
    rows = len(plate)
    gone = lambda v: v in EYE_INDEX or v in RING_INDEX
    for x in range(len(plate[0])):
        ys = [y for y in range(rows) if gone(plate[y][x])]
        if not ys:
            continue
        lo, hi = min(ys), max(ys)
        above = plate[lo - 1][x] if lo > 0 else plate[hi + 1][x]
        below = plate[hi + 1][x] if hi + 1 < rows else above
        for y in ys:
            out[y][x] = above if y < (lo + hi) / 2 else below
    return out


def frame(plate, state):
    """The plate with its lid at `state` (a new grid)."""
    if state == OPEN:
        return [row[:] for row in plate]
    skin = _skin_rows(plate)
    out = [row[:] for row in plate]
    ox, oy = PLATE_AT
    for y in range(PLATE_SIZE[1]):
        for x in range(PLATE_SIZE[0]):
            wx, wy = ox + x, oy + y
            if plate[y][x] not in EYE_INDEX and plate[y][x] not in RING_INDEX:
                continue
            if state == HALF:
                d = (wx - EYE_X) / EYE_A
                edge = LID_Y + int(round(-3 * d + 2.0 * d * d))       # the edge slopes with the tilted eye and bows at the sides
                if wy < edge:
                    out[y][x] = skin[y][x]
                elif wy == edge:
                    out[y][x] = LASH
            else:
                out[y][x] = skin[y][x]
    if state == SHUT:
        for x in range(PLATE_SIZE[0]):
            wx = ox + x
            d = (wx - EYE_X) / EYE_A
            if abs(d) <= 1:
                line = SHUT_Y + int(round(-4 * d + SHUT_SAG * (1 - d * d)))
                for wy in (line, line + 1):
                    out[wy - oy][x] = LASH
    return out


def stamp(tim):
    """The three frames into their spare texels (in place); the open frame is a copy of the painted plate."""
    plate = _grab(tim, PLATE_AT, PLATE_SIZE)
    for state, at in enumerate(FRAMES):
        _put(tim, at, frame(plate, state))
    return plate


# ------------------------------------------------------------------ what the clips do
def _move(src, dst):
    return dict(src=(src[0] // 4, src[1]), size=(PLATE_SIZE[0] // 4, PLATE_SIZE[1]), dst=(dst[0] // 4, dst[1]))


def eye_move(state):
    return _move(FRAMES[state], PLATE_AT)


def blink(at, slow=False):
    """Eye states (tick, state) of one blink starting at `at`, back to open; slow = a heavier, tired blink."""
    if slow:
        return [(at, HALF), (at + 1, SHUT), (at + 4, SHUT), (at + 5, HALF), (at + 7, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 2, HALF), (at + 3, OPEN)]


def events(eyes, ticks, eye0=OPEN):
    """Texture-move events (tick, 'tex', move): the clip's first face at tick 0, then every change of the plan, which
    must be inside the clip, in order, and end in the first face so the loop closes."""
    assert all(0 < t < ticks for t, _ in eyes), 'face changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'face changes in order'
    assert not eyes or eyes[-1][1] == eye0, 'a clip must end with its first face'
    return [(0, 'tex', eye_move(eye0))] + [(t, 'tex', eye_move(k)) for t, k in eyes]
