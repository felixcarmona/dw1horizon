"""FI_INFO triangle-label allocation, in TIM pixels (sprite V stores row + 1).

The five 32x16 clock frames occupy the rest of u128..191; never clear
that whole strip. See docs/mods/clock-labels.md for the draw-site audit.
"""
CLOCK_FRAMES = ((128, 0, 32, 16), (160, 0, 32, 16), (128, 16, 32, 16),
                (160, 16, 32, 16), (128, 32, 32, 16))
# entry -> (Spanish catalog key, u, row); shared by every translated language.
CELLS = {1: ('OBJETOS', 128, 48), 3: ('JUGADOR', 160, 32),
         4: ('ALABAR', 128, 55), 6: ('DORMIR', 160, 39),
         7: ('PESCAR', 160, 55), 5: ('REÑIR', 160, 46)}
SHARED_SIZES = {e: (32, 9 if e == 5 else 7) for e in CELLS}


def overlaps(a, b):
    x, y, w, h = a
    u, v, rw, rh = b
    return x < u + rw and u < x + w and y < v + rh and v < y + h


def check_cells(rects):
    for i, rect in enumerate(rects):
        x, y, w, h = rect
        if not (128 <= x < x + w <= 192 and 32 <= y < y + h <= 64):
            raise ValueError(f'FI_INFO label outside allocation: {rect}')
        if any(overlaps(rect, frame) for frame in CLOCK_FRAMES):
            raise ValueError(f'FI_INFO label overlaps clock frame: {rect}')
        if any(overlaps(rect, other) for other in rects[:i]):
            raise ValueError(f'FI_INFO labels overlap: {rect}')


def check_clock(base, generated, entry=0):
    """Compare every day/night frame's indices against this player's base TIM."""
    from tools.localize.build import tim_entries
    def frames(data):
        start, bpp, w, h = tim_entries(data)[entry]
        if bpp != 0:
            raise ValueError('FI_INFO must be 4-bit indexed')
        return bytes((data[start + y * w // 2 + x // 2] >> (4 * (x & 1))) & 15
                     for u, v, rw, rh in CLOCK_FRAMES
                     for y in range(v, v + rh) for x in range(u, u + rw))
    if frames(base) != frames(generated):
        raise ValueError('FI_INFO localization changed a clock animation frame')
