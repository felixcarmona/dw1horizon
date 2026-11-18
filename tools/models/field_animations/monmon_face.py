"""Monmon's (species 352) blink: texture frames in the free rows of its texture, and the schedule that copies them over the
painted eye.

The head has no eyelid or eye bone and no separate eye mesh: the eye is a 14 pixel ring (black rim, white, grey iris, black
pupil) painted on the head's texture, on one quad drawn on both sides of the face. The engine copies rectangles inside the
model's own texture slot while a clip plays (texture-move instructions, the way the original Digimon blink), so the face
blinks by pasting a lid frame over the painted eye: no mesh, skeleton or palette change, and no extra bone.

Texture layout (pixels; the texture is 256x128, 4 bits; its rows 0..63 are the model, rows 64 down are the empty filler):
  eye block    (232, 16)  16x16  the painted eye (x 232-245, y 17-30) in its skin (palette row 1, index 5 is the skin)
  eye frames   row 80, x = 0, 16, 32: open (a copy of the painted block), half shut, shut.
A half-shut eye has the skin over its upper half and a dark lid line; a shut one is the skin with a curved lash line.
Texture moves copy index pixels only, so every frame uses the colours of the palette row of the block it is drawn over.
"""

W = 256
EYE_AT, EYE_SIZE = (232, 16), (16, 16)
FRAME_Y = 80
EYE_FRAMES = (0, 16, 32)                 # open, half shut, shut
OPEN, HALF, SHUT = 0, 1, 2
SKIN, SKIN_SHADE, SOFT, LASH = 5, 6, 8, 11   # palette row 1: the skin, a darker skin, a brown shade, the black of the rim
FILLER = 15


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def eye_frame(block, state):
    """The open block -> its half-shut or shut frame (the ring is x 0-13, y 1-14 of the block, centre 6.5, 7.5)."""
    if state == OPEN:
        return [r[:] for r in block]
    out = [[SKIN] * len(block[0]) for _ in block]
    if state == HALF:
        # the lower half of the eye stays: the lid covers every row above its edge, a lash line runs along the edge
        edge = {x: 8 - (1 if x in (0, 1, 12, 13) else 0) for x in range(14)}
        for y in range(len(block)):
            for x in range(14):
                if y > edge[x]:
                    out[y][x] = block[y][x]
        for x in range(14):
            out[edge[x]][x] = LASH if 1 <= x <= 12 else SOFT
        for x in range(2, 12):
            out[edge[x] - 1][x] = SOFT       # the lid's lower rim, a soft brown line over the black one
        return out
    for x in range(1, 13):                      # shut: the lash curves down at the middle, ends lifted
        d = 1 - ((x - 6.5) / 5.5) ** 2
        y = int(round(10 + 2.0 * d))
        out[y][x] = LASH
        if x in (2, 11):
            out[y - 1][x] = SOFT
        if 3 <= x <= 10:
            out[y + 1][x] = SOFT if x not in (6, 7) else SKIN_SHADE
    return out


def stamp(tim):
    """Paste the three frames into the free rows (in place); the texture's other texels do not change."""
    block = _grab(tim, EYE_AT, EYE_SIZE)
    assert all(v == FILLER for v in tim.idx[(FRAME_Y - 16) * W:]), 'rows 64 down of the texture must be free'
    for state, x in enumerate(EYE_FRAMES):
        _put(tim, (x, FRAME_Y), eye_frame(block, state))


# ------------------------------------------------------------------ what the clips do
def eye_move(state):
    return dict(src=(EYE_FRAMES[state] // 4, FRAME_Y), size=(EYE_SIZE[0] // 4, EYE_SIZE[1]), dst=(EYE_AT[0] // 4, EYE_AT[1]))


def blink(at, slow=False):
    """Eye states (tick, state): half shut, shut, half shut, open; a slow (tired) blink stays shut longer."""
    if slow:
        return [(at, HALF), (at + 1, SHUT), (at + 4, SHUT), (at + 5, HALF), (at + 6, OPEN)]
    return [(at, HALF), (at + 1, SHUT), (at + 2, HALF), (at + 3, OPEN)]


def events(eyes, ticks):
    """Texture-move events (tick, 'tex', move): the open eye at tick 0, then every change of the plan (tick, state), inside
    the clip, in order; the plan ends open so that the loop closes and a clip cut in the middle of a blink is repaired by
    the next one."""
    assert all(0 < t < ticks for t, _ in eyes), 'eye changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'eye changes in order'
    assert not eyes or eyes[-1][1] == OPEN, 'a clip must end with the eyes open'
    return [(0, 'tex', eye_move(OPEN))] + [(t, 'tex', eye_move(k)) for t, k in eyes]
