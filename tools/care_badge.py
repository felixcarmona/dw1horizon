"""Derive the care-only Square cap from the player's native UI button frames.

The ordinary SYSTEM_W upload loads these pixels and palette with the field UI.
No artwork, painter, upload buffer or extra file needs to live in the executable.
"""
import struct

from tools.localize.systemw import CARE_BUTTON_RECTS, CARE_BUTTON_GUARD_RECTS

FILES = (('ETCDAT/SYSTEM_W.TIM', 0), ('ETCDAT/ETCTIM.BIN', 8))
SQUARE = ('LLLLLL', 'L....D', 'L....D', 'L....D', 'LDDDDD')


def _tim(data, entry):
    offset = 0
    for index in range(entry + 1):
        magic, flags = struct.unpack_from('<II', data, offset)
        if magic != 0x10:
            raise ValueError('invalid TIM stack')
        clut = offset + 8
        pixel = clut
        if flags & 8:
            length, cx, cy, cw, ch = struct.unpack_from('<IHHHH', data, clut)
            pixel += length
        size, x, y, w, h = struct.unpack_from('<IHHHH', data, pixel)
        if index == entry:
            if flags != 8:
                raise ValueError('care badge needs a 4-bit TIM with a palette')
            if (x, y, w, h) != (320, 128, 64, 128) or not (cx <= 96 and cy <= 500 < cy + ch and cw >= 16):
                raise ValueError('unexpected SYSTEM_W texture or palette placement')
            return pixel + 12, w, clut + 12 + ((500 - cy) * cw + 96 - cx) * 2
        offset = (pixel + size + 3) & ~3


def _frames(read):
    original = [[[read(76 + frame * 16 + x, 55 + y) for x in range(16)]
                 for y in range(12)] for frame in range(3)]
    for japanese in (False, True):
        ink = {7, 14, 15} if japanese else {12, 13}
        other = {12, 13} if japanese else {7, 14, 15}
        result = []
        for frame in original:
            dots = [(x, y) for y, row in enumerate(frame) for x, value in enumerate(row) if value in ink]
            if not dots or any(value in other for row in frame for value in row):
                break
            left = min(x for x, y in dots)
            top = min(y for x, y in dots)
            if max(x for x, y in dots) - left != (7 if japanese else 5) or max(y for x, y in dots) - top != 4:
                break
            cap = [[3 if value in ink else value for value in row] for row in frame]
            for y, row in enumerate(SQUARE):
                for x, value in enumerate(row):
                    if value != '.':
                        cap[top + y][left + japanese + x] = 12 if value == 'L' else 13
            result.append(cap)
        if len(result) == 3:
            return result
    raise ValueError('unrecognized native Cross/Circle cap')


def stamp(data, entry=0):
    """Change only the reserved care cells in a TIM/stack, preserving native Confirm."""
    pixels, words, clut = _tim(data, entry)
    stride = words * 2

    def read(x, y):
        return (data[pixels + y * stride + x // 2] >> (4 * (x & 1))) & 15

    def write(x, y, value):
        offset = pixels + y * stride + x // 2
        shift = 4 * (x & 1)
        data[offset] = (data[offset] & ~(15 << shift)) | (value << shift)

    frames = _frames(read)
    palette = list(struct.unpack_from('<16H', data, clut))
    palette[7] = palette[14] = palette[15] = 0
    palette[12:14] = [0x621f, 0x3d14]
    if palette[8] != 0:
        raise ValueError('native cap transparency changed')
    for u, v, w, h in CARE_BUTTON_GUARD_RECTS:
        if any(palette[read(x, y)] for y in range(v, v + h) for x in range(u, u + w)):
            raise ValueError('care UV guard column is not transparent')
    for frame, (u, v, w, h) in zip(frames, CARE_BUTTON_RECTS):
        for y in range(h):
            # Right-edge cells omit transparent column zero: U239..255 cannot wrap.
            row = frame[y] if u == 192 else frame[y][1:] + [8]
            for x in range(w):
                write(u + x, v + y, row[x])
    # VRAM (352,252) lies inside the existing TIM's pixel upload, not its CLUT block.
    struct.pack_into('<16H', data, pixels + 124 * stride + 32 * 2, *palette)
