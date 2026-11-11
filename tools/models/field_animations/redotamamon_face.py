"""RedOtamamon's (species 233) eyes: blinks and heavy lids through texture moves.

The tadpole has no eyelid bone: its eye is painted on the head's texture, one 40x40 plate (x 88-127, y 32-71) that the
head wraps around both eyes (a fan of faces around the middle of the eyeball). While a clip plays the engine can copy a
rectangle inside the model's own texture slot (texture-move instructions, the way every original Digimon blinks), so the
eye acts by pasting a frame over that plate: no mesh, skeleton or palette change.

The texture is 256x128 and nothing is drawn right of x = 132, so the three frames live there:
  open  (136, 32)  a copy of the painted plate (a clip's first face, and the way back from the others)
  half  (176, 32)  the lid down over the top of the eyeball, a dark lash line along its edge
  shut  (216, 32)  the eyeball covered by skin with a curved lash line
Each frame is made from the painted plate: the eyeball's ellipse is repainted in the skin colour of its own surround above
the lid line, nothing else moves. Texture moves copy index pixels only, so every frame keeps the palette row it is drawn with.
"""

W = 256
PLATE_AT, PLATE_SIZE = (88, 32), (40, 40)
FRAMES = ((136, 32), (176, 32), (216, 32))            # open, half, shut
OPEN, HALF, SHUT = 0, 1, 2

SKIN, LASH = 12, 14                                   # palette indices: the socket's skin, its darkest line
EYE_X, EYE_Y = 106.5, 59.0                            # the eyeball's middle
EYE_A = 12.6                                          # its half width
EYE_BOX = (92, 48, 122, 72)                           # x0, y0, x1, y1 (end excluded): the painted eyeball and its outline
EYE_INDEX = {1, 2, 3, 4, 5, 13, 14}                   # the white, the iris and pupil, the outline (never the skin's 12)
LID = {HALF: 56}                                      # y of the lid's edge at the middle of the eyeball
SHUT_Y, SHUT_SAG = 57, 3                              # the shut lash line: its y at the ends and how far it sags


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _eyeball(plate, x, y):
    """Whether the plate's texel at texture (x, y) belongs to the painted eyeball."""
    x0, y0, x1, y1 = EYE_BOX
    return x0 <= x < x1 and y0 <= y < y1 and plate[y - PLATE_AT[1]][x - PLATE_AT[0]] in EYE_INDEX


def frame(plate, state):
    """The plate with its lid at `state` (a new grid)."""
    out = [row[:] for row in plate]
    if state == OPEN:
        return out
    ox, oy = PLATE_AT
    for y in range(PLATE_SIZE[1]):
        for x in range(PLATE_SIZE[0]):
            wx, wy = ox + x, oy + y
            if not _eyeball(plate, wx, wy):
                continue
            if state == HALF:
                edge = LID[HALF] + int(round(1.5 * ((wx - EYE_X) / EYE_A) ** 2))     # the edge bows down at the sides
                if wy < edge:
                    out[y][x] = SKIN
                elif wy == edge:
                    out[y][x] = LASH
            else:
                out[y][x] = SKIN
    if state == SHUT:
        for x in range(PLATE_SIZE[0]):
            wx = ox + x
            d = (wx - EYE_X) / EYE_A
            if abs(d) <= 1:
                line = SHUT_Y + int(round(SHUT_SAG * (1 - d * d)))
                for wy in (line, line + 1):
                    out[wy - oy][x] = LASH
    return out


def stamp(tim):
    """The three frames into the free right side (in place); the open frame is checked against the painted plate."""
    plate = _grab(tim, PLATE_AT, PLATE_SIZE)
    for at in FRAMES:
        assert not any(v for row in _grab(tim, at, PLATE_SIZE) for v in row), 'the frame slots must be free'
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
