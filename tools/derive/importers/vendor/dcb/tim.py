"""TIM images (the model textures are 4bpp with their CLUTs in the same file)."""
import struct
from dataclasses import dataclass

from tools.derive import arraymath as np


@dataclass
class Tim:
    bpp: int
    clut_xy: tuple
    clut: np.ndarray       # (rows, colours) uint16
    image_xy: tuple
    pixels: np.ndarray     # (h, w) palette indices (4/8bpp) or 16-bit colours


def parse_tim(d, p=0):
    magic, flags = struct.unpack_from("<II", d, p)
    if magic != 0x10:
        raise ValueError("not a TIM")
    q = p + 8
    bpp = {0: 4, 1: 8, 2: 16, 3: 24}[flags & 3]
    clut_xy, clut = (0, 0), np.zeros((0, 0), np.uint16)
    if flags & 8:
        size, x, y, w, h = struct.unpack_from("<I4H", d, q)
        clut_xy = (x, y)
        clut = np.frombuffer(d, np.uint16, w * h, q + 12).reshape(h, w)
        q += size
    size, x, y, w, h = struct.unpack_from("<I4H", d, q)
    raw = np.frombuffer(d, np.uint8, w * h * 2, q + 12).reshape(h, w * 2)
    if bpp == 4:
        from tools.derive.texture import indices4
        pixels = indices4(d[q + 12:q + 12 + w * h * 2], h, w * 4)
    elif bpp == 8:
        pixels = raw
    else:
        pixels = raw.view(np.uint16)
    tim = Tim(bpp, clut_xy, clut, (x, y), pixels)
    tim.packed = np.frombuffer(d, np.uint16, w * h, q + 12).reshape(h, w)
    return tim


def rgba(colours):
    """PS1 15-bit colours -> RGBA uint8; 0x0000 is transparent."""
    from tools.derive.texture import rgba15
    return rgba15(np.asarray(colours, np.uint32), replicate=True)


def render(tim, clut_row):
    """The image with one of its CLUT rows applied, as RGBA."""
    return rgba(tim.clut[clut_row][tim.pixels])
