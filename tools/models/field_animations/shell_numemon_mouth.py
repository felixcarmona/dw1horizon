"""ShellNumemon's (species 231) mouth opens and shuts through texture moves.

The mouth has no jaw: its upper teeth are painted on a small plate (bone 9) hung from the head and its lower teeth on
the front of the foot (bone 3), the two pictures side by side in the texture. Turning the plate would open the ring of
vertices it shares with the head and the foot, so the mouth acts by pasting frames over the two pictures instead (the
engine copies rectangles inside the model's own texture slot while a clip plays, the way every original Digimon
blinks): no mesh, skeleton or palette change.

Texture layout (pixels; the texture is 256x128, the teeth use palette row 3):
  mouth         (224, 96) 32x12: x 224-239 the upper teeth (their tips at the bottom), x 240-255 the lower teeth
                (their tips at the top)
  mouth frames  row 116, x = 104, 136, 168: the mouth as painted (a backup), half open, open. The rows there are
                blank or hold a few stray texels that no face samples.
A frame opens the mouth by sliding the upper teeth up and the lower teeth down by the same number of texels; the rows
they uncover between them are the dark inside of the mouth.
"""

W = 256
MOUTH_AT, MOUTH_SIZE = (224, 96), (32, 12)
HALF_WIDTH = 16                                   # the upper teeth, then the lower teeth
FRAMES_Y = 116
FRAMES = ((104, FRAMES_Y), (136, FRAMES_Y), (168, FRAMES_Y))   # rest, half, open
REST, HALF, OPEN = 0, 1, 2
SLIDE = {REST: 0, HALF: 2, OPEN: 4}               # texels each row of teeth moves away from the other
INSIDE = 2                                        # palette index of the mouth's inside (black, as between the teeth)


def _grab(tim, at, size):
    return [[tim.idx[(at[1] + y) * W + at[0] + x] for x in range(size[0])] for y in range(size[1])]


def _put(tim, at, rows):
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            tim.idx[(at[1] + y) * W + at[0] + x] = v


def mouth_frame(rest, slide):
    """The painted mouth with the upper teeth slid up and the lower teeth slid down by `slide` texels."""
    h = len(rest)
    out = []
    for y in range(h):
        upper = rest[y + slide][:HALF_WIDTH] if y + slide < h else [INSIDE] * HALF_WIDTH
        lower = rest[y - slide][HALF_WIDTH:] if y >= slide else [INSIDE] * HALF_WIDTH
        out.append(list(upper) + list(lower))
    return out


def stamp(tim):
    """The mouth frames into row 116 (in place); the painted mouth is left as it is."""
    for at in FRAMES:
        assert not any(tim.idx[(at[1] + y) * W + at[0] + x] for y in range(MOUTH_SIZE[1]) for x in range(28)), \
            'the frame rows must be blank'
    rest = _grab(tim, MOUTH_AT, MOUTH_SIZE)
    for state, at in enumerate(FRAMES):
        _put(tim, at, mouth_frame(rest, SLIDE[state]))


def move(state):
    """The texture-move instruction that shows `state` (x and widths in 16-bit VRAM units, 4 texels each)."""
    src = FRAMES[state]
    return dict(src=(src[0] // 4, src[1]), size=(MOUTH_SIZE[0] // 4, MOUTH_SIZE[1]),
                dst=(MOUTH_AT[0] // 4, MOUTH_AT[1]))


def events(plan, ticks):
    """Texture-move events (tick, 'tex', move): the shut mouth at tick 0, then every change of the plan, which must
    shut the mouth again before the last tick (a clip that is cut short leaves the mouth as it was, so every clip
    starts by shutting it)."""
    assert all(0 < t < ticks for t, _ in plan), 'mouth changes inside the clip'
    assert [t for t, _ in plan] == sorted(t for t, _ in plan), 'mouth changes in order'
    assert not plan or plan[-1][1] == REST, 'a clip must end with the mouth shut'
    return [(0, 'tex', move(REST))] + [(t, 'tex', move(k)) for t, k in plan]
