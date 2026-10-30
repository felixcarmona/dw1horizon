"""Model textures: the TIM at the end of a model file. It is 4bpp; its own CLUT
block is never uploaded by the game (Gfx_LoadTexSlotImage only loads CLUTs of
8bpp images). The palettes live in the image itself: a primitive's clut field is
row << 6 | x / 16 relative to the image, 16 colours each."""
import struct

from tools.derive import arraymath as np


def image_halfwords(tim):
    magic, flags = struct.unpack_from("<2I", tim, 0)
    assert magic == 0x10 and flags & 7 == 0, "expected a 4bpp TIM"
    p = 8
    if flags & 8:
        p += struct.unpack_from("<I", tim, p)[0]
    _size, _x, _y, w, h = struct.unpack_from("<I4H", tim, p)
    return np.frombuffer(tim, "<u2", w * h, p + 12).reshape(h, w)


def rgba15(c):
    c = np.asarray(c, dtype=np.uint32)
    rgb = np.stack([c & 0x1F, (c >> 5) & 0x1F, (c >> 10) & 0x1F], axis=-1) * 255 // 31
    alpha = np.where(c == 0, 0, 255)[..., None]
    return np.concatenate([rgb, alpha], axis=-1).astype(np.uint8)


def render(tim, clut):
    """The texture as RGBA with the palette a primitive's clut field names."""
    hw = image_halfwords(tim)
    row, x = clut >> 6, (clut & 0x3F) * 16
    pal = rgba15(hw[row % hw.shape[0], x:x + 16])
    idx = np.empty((hw.shape[0], hw.shape[1] * 4), np.uint8)
    for i in range(4):
        idx[:, i::4] = (hw >> (4 * i)) & 0xF
    return pal[idx]
