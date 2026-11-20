"""The hair's strand texture: a 48x14 tile in the layout rectangle of the tamer texture, drawn with its own palette row.

The tile holds tone numbers 1..15 (0 is transparent). LEVELS gives each tone's brightness, 128 = the hair colour
itself: the game writes the palette row as colour * level / 128 for the chosen colour.
"""
import random

from .wig import HAIR_ROW, U0, V0, UW, VH

MIDDLE = 9                    # the tone of plain hair
CONTRAST = 0.7                # the strand tones are pulled towards the middle one
RAMP = (0, 40, 52, 64, 76, 88, 100, 112, 124, 136, 150, 164, 180, 198, 218, 240)
LEVELS = tuple(l if i < 6 else round(RAMP[MIDDLE] + (l - RAMP[MIDDLE]) * CONTRAST) for i, l in enumerate(RAMP))
LOCK = (-2, -1, 0, 1, 1, 0)   # across one lock: the parting, the lit middle, the soft far side
UNDERSIDE = 3
DEFAULT = (120, 84, 48)


def colour15(rgb, level):
    """One palette entry the way the game computes it (never 0: that is the transparent colour)."""
    r, g, b = (min(31, (c * level // 128 + 4) >> 3) for c in rgb)
    return 0x8000 | r | g << 5 | b << 10


def palette(rgb):
    return [0] + [colour15(rgb, l) for l in LEVELS[1:]]


def paint(tex):
    tex.idx = bytearray(tex.idx)
    tex.pal[HAIR_ROW] = palette(DEFAULT)
    rnd = random.Random(7)
    for band in range(8):      # each six-texel band is one segment of the head, painted as one lock
        shift = rnd.choice((0, 0, 1))
        lock = [LOCK[(x - shift) % 6] for x in range(6)]
        ends = [VH - rnd.choice((2, 3, 4)) for _ in range(6)]
        for x in range(6):
            u = U0 + band * 6 + x
            for y in range(VH):
                v = MIDDLE + lock[x]
                if 3 <= y <= 5 and lock[x] >= 0:
                    v += 2 if y == 4 else 1            # the sheen ring
                if y <= 1:
                    v -= 1                             # the crown
                if y >= ends[x]:
                    v -= 1 + (y - ends[x])             # the ends darken, each strand at its own height
                if u >= U0 + 46:
                    v = UNDERSIDE
                tex.idx[(V0 + y) * tex.w + u] = max(1, min(15, v))
