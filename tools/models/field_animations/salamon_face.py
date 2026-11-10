"""Salamon's (species 221) blink: texture frames in the free rows of its texture, and the schedule that copies them over the
painted eye.

The head has no eye or lid bone: one eye sprite is painted on the head's texture and drawn on both sides of the face. The
engine copies rectangles inside the model's own texture slot while a clip plays (texture-move instructions, the way every
original Digimon blinks), so the face acts by pasting a new frame over the sprite: no mesh, skeleton or palette change
(gomamon_face.py does the same for Gomamon).

Texture layout (pixels, the texture is 256x128; its used part, rows 0..51, is unchanged):
  eye rectangle (16, 6)  28x20  the eye and a margin of skin (palette row 0)
  frames        row 80 down, in the free rows: eye open (a backup of the sprite), half shut, shut; x = 0, 28, 56.
Texture moves copy index pixels only, so every frame uses the palette row of the sprite it replaces. The skin under the
lids is made from the skin around the eye (each row blends the shade left of the eye into the shade right of it), so the
frames use only the colours the face already has.
"""
import math

EYE_AT, EYE_SIZE = (16, 6), (28, 20)
FRAME_Y = 80
EYE_FRAMES = (0, 28, 56)          # open, half, shut
W = 256
OUTLINE, SOFT = 9, 10             # the eye's black and its dark grey (palette row 0)
LEFT, RIGHT = 1, 25               # the first and last columns of the eye rectangle that carry the eye (x - 16)


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def _skin(open_eye):
    """The rectangle with the skin only: every row slides from the shade just left of the eye to the shade at its
    right edge."""
    h, w = len(open_eye), len(open_eye[0])
    out = []
    for y in range(h):
        a, b = open_eye[y][LEFT - 1], open_eye[y][RIGHT + 1]
        row = list(open_eye[y])
        for x in range(LEFT, RIGHT + 1):
            row[x] = int(round(a + (b - a) * (x - LEFT + 1) / (RIGHT - LEFT + 2)))
        out.append(row)
    return out


def _line(px, curve, thick):
    for x, y in curve:
        for dy in range(-thick, thick + 1):
            yy = int(round(y)) + dy
            if 0 <= yy < len(px) and 0 <= x < len(px[0]):
                px[yy][x] = OUTLINE if abs(dy) < thick else SOFT


def _sag(x0, x1, y, depth):
    mid, half = (x0 + x1) / 2, (x1 - x0) / 2
    return [(x, y + depth * (1 - ((x - mid) / half) ** 2)) for x in range(x0, x1 + 1)]


def eye_frames(open_eye):
    """(half shut, shut): the upper lid drawn over the open eye, then the whole eye wiped to a closed line."""
    skin = _skin(open_eye)
    x0, x1 = LEFT + 1, RIGHT - 1
    lid = _sag(x0, x1, 8.2, 2.6)             # the lid's edge: low in the middle, higher at the corners
    top = {x: y for x, y in lid}
    half = [r[:] for r in open_eye]
    for y, row in enumerate(half):
        for x in range(LEFT, RIGHT + 1):
            if x in top and y <= top[x]:
                row[x] = skin[y][x]
    _line(half, lid, 1)
    shut = [r[:] for r in skin]
    _line(shut, _sag(x0 + 1, x1 - 1, 9.4, 3.0), 1)
    return half, shut


def stamp(tim):
    """Paste the three frames into the free rows (in place); the texture's other texels do not change."""
    eye = _grab(tim, EYE_AT, EYE_SIZE)
    assert not any(tim.idx[FRAME_Y * W:]), 'rows 80 down of the texture must be free'
    half, shut = eye_frames(eye)
    for x, frame in zip(EYE_FRAMES, (eye, half, shut)):
        _put(tim, (x, FRAME_Y), frame)


# ------------------------------------------------------------------ what the clips do
def eye_move(state):
    return dict(src=(EYE_FRAMES[state] // 4, FRAME_Y), size=(EYE_SIZE[0] // 4, EYE_SIZE[1]), dst=(EYE_AT[0] // 4, EYE_AT[1]))


def blink(at, slow=False):
    """Eye states (tick, 0 open | 1 half | 2 shut): half, shut, half, open; slow = a tired, heavier blink."""
    if slow:
        return [(at, 1), (at + 1, 2), (at + 3, 2), (at + 4, 1), (at + 5, 0)]
    return [(at, 1), (at + 1, 2), (at + 2, 1), (at + 3, 0)]


def events(eyes, ticks):
    """Texture-move events (tick, 'tex', move): the open eye first, then the plan; every state change inside the clip and
    the clip ends open-eyed (the plan must finish with state 0 before the last tick)."""
    assert eyes[-1][1] == 0 and eyes[-1][0] < ticks, 'a clip must end with the eyes open'
    return [(t, 'tex', eye_move(k)) for t, k in [(0, 0)] + list(eyes)]
