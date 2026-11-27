"""Veemon's (species 180) blinking eyes, through texture moves.

The head has no eyelid bone or eye piece: both eyes are one painted block of the Digimon World 2 texture. DW2 blinks it
itself (a texture-animation part: a destination and three frames, open, half shut and shut), and tools/dw2mmd.py keeps
the part as it is (`model.blinks`), so the frames are DW2's own art: nothing is drawn or stamped here. A clip pastes a
frame over the block with texture-move instructions (the way every original Digimon blinks): no mesh, skeleton or palette
change.

Texture layout (pixels; the converted texture is 256x128, 4 bits):
  eye block   (12, 0)  36x36  the painted eyes (DW2's texAnimParts destination)
  eye frames  (72, 36) open, (36, 36) half shut, (0, 36) shut.
Texture moves copy index pixels only, so every frame keeps the palette row of the block it is drawn over.
"""
W = 256
EYE_AT, EYE_SIZE = (12, 0), (36, 36)
EYE_FRAMES = ((72, 36), (36, 36), (0, 36))               # open, half shut, shut
OPEN, HALF, SHUT = 0, 1, 2


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


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
