"""Model textures: a TIM flagged as 16-bit 64x256 that really holds a 256x256 4bpp
image. The CLUTs live in the same image, in its bottom rows: a material header
points at one with (x, y) in 16-bit units, 16 colours per CLUT."""
import struct

from tools.derive import arraymath as np


def tim_halfwords(tim):
    """Return the TIM pixel block as a (height, width) uint16 array."""
    magic, flags = struct.unpack_from("<2I", tim, 0)
    assert magic == 0x10 and flags == 2, "expected a 16-bit TIM without CLUT"
    _size, _x, _y, w, h = struct.unpack_from("<I4H", tim, 8)
    return np.frombuffer(tim, dtype="<u2", count=w * h, offset=20).reshape(h, w)


def indices_4bpp(halfwords):
    """Split each 16-bit word into four 4-bit pixels, low nibble first."""
    from tools.derive.texture import indices4
    h, w = halfwords.shape
    return indices4(halfwords.tobytes(), h, w * 4)


def clut_rgba(halfwords, x, y):
    """16 colours from (x, y) as RGBA. 0x0000 is the PS1's transparent colour."""
    c = halfwords[y, x:x + 16].astype(np.uint32)
    r, g, b = c & 0x1F, (c >> 5) & 0x1F, (c >> 10) & 0x1F
    rgba = np.stack([r, g, b, np.full_like(r, 31)], axis=1) * 255 // 31
    rgba[c == 0, 3] = 0
    return rgba.astype(np.uint8)


def render(tim, clut_xy):
    """The 256x256 texture coloured with the CLUT at clut_xy, as an RGBA array."""
    hw = tim_halfwords(tim)
    return clut_rgba(hw, *clut_xy)[indices_4bpp(hw)]
