"""Veemon's (species 180) blinking eyes, through texture moves.

The head has no eyelid bone or eye piece: both eyes are one painted block (a black oval with a red rim, a white glint at the
top and two smaller ones at the bottom) drawn on both sides of the face (the head's quad at u 22-46, v 0-39, palette row 7).
A clip pastes a frame over the block with texture-move instructions (the way every original Digimon blinks): no mesh,
skeleton or palette change.

Texture layout (pixels; the texture is 256x128, 4 bits; the free texels are sampled by no triangle of the model):
  eye block   (20, 0)  28x40  the painted eyes and the skin around them, which every frame keeps
  eye frames  (204, 36) open (a copy of the painted block), (200, 76) half shut, (228, 76) shut.
Texture moves copy index pixels only, so every frame keeps the palette row of the block it is drawn over.
"""
W = 256
EYE_AT, EYE_SIZE = (20, 0), (28, 40)
EYE_FRAMES = ((204, 36), (200, 76), (228, 76))               # open, half shut, shut
OPEN, HALF, SHUT = 0, 1, 2
SKIN = (0xd, 0xe, 0xf)                    # palette row 7: the skin around the eyes
DARK = 1                                  # the outline and the pupil
LID_ROWS = {HALF: 15, SHUT: 20}           # the lid line's middle row


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _eye_mask(block):
    """Which texels of the quad (x 22-47, y 0-37) are the eye and its shadowed rim: everything but the two lighter skin tones."""
    return {(x, y) for y in range(38) for x in range(2, 28) if block[y][x] not in (0xd, 0xe)}


def _lid_row(state, x):
    d = (x - 14.5) / 12.5
    return LID_ROWS[state] + (4.0 if state == SHUT else 2.5) * (1 - d * d)


def eye_frame(block, state):
    """The painted block as a frame: half shut (skin over the eye's upper part, a lid line along its edge) or shut (all of
    the eye replaced by skin, a dark curve bowed down in the middle with a hint of the red rim under it)."""
    out = [row[:] for row in block]
    mask = _eye_mask(block)
    for (x, y) in mask:
        if state == SHUT or y < _lid_row(state, x):
            out[y][x] = 0xd if y < 8 else (0xe if y < 26 else 0xf)      # the face's skin runs from light (brow) to dark (cheek)
    for x in range(3, 27):
        d = (x - 14.5) / 12.5
        if abs(d) > 0.97:
            continue
        top = int(round(_lid_row(state, x)))
        thick = 4 if abs(d) < 0.7 else 3
        for k in range(thick):
            out[top + k][x] = DARK
        if state == SHUT and abs(d) < 0.75:
            out[top + thick][x] = 2
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
    the clip, in order, ending in its first state so that the loop closes."""
    assert all(0 < t < ticks for t, _ in eyes), 'eye changes inside the clip'
    assert [t for t, _ in eyes] == sorted(t for t, _ in eyes), 'eye changes in order'
    assert not eyes or eyes[-1][1] == eye0, 'a clip must end with its first face'
    return [(0, 'tex', eye_move(eye0))] + [(t, 'tex', eye_move(k)) for t, k in eyes]
