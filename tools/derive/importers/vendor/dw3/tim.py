"""Plain PlayStation TIM images (4/8 bpp with CLUT, 15/24 bpp direct)."""
import struct

from tools.derive import arraymath as np


def is_tim(data):
    if len(data) < 20:
        return False
    magic, flags = struct.unpack_from("<2I", data, 0)
    if magic != 0x10 or flags & ~0xF:
        return False
    # The CLUT and image blocks must add up to (at most) the data's length.
    p = 8
    for _ in range(2 if flags & 8 else 1):
        if p + 12 > len(data):
            return False
        size, _x, _y, w, h = struct.unpack_from("<I4H", data, p)
        if size != 12 + w * h * 2 or w == 0 or h == 0:
            return False
        p += size
    return p <= len(data)


def rgba15(c):
    """PS1 15-bit colours to RGBA; 0x0000 is the transparent colour."""
    c = np.asarray(c, dtype=np.uint32)
    rgb = np.stack([c & 0x1F, (c >> 5) & 0x1F, (c >> 10) & 0x1F], axis=-1) * 255 // 31
    alpha = np.where(c == 0, 0, 255)[..., None]
    return np.concatenate([rgb, alpha], axis=-1).astype(np.uint8)


def decode(data, clut_index=0):
    """Decode a TIM to an (h, w, 4) RGBA array, using CLUT row `clut_index`."""
    flags = struct.unpack_from("<I", data, 4)[0]
    bpp, p = flags & 7, 8
    clut = None
    if flags & 8:
        size, _x, _y, cw, ch = struct.unpack_from("<I4H", data, p)
        clut = np.frombuffer(data, "<u2", cw * ch, p + 12).reshape(ch, cw)
        p += size
    _size, _x, _y, w, h = struct.unpack_from("<I4H", data, p)
    p += 12
    raw = np.frombuffer(data, np.uint8, w * h * 2, p).reshape(h, w * 2)
    if bpp == 0:
        idx = np.empty((h, w * 4), np.uint8)
        idx[:, 0::2], idx[:, 1::2] = raw & 0xF, raw >> 4
        return rgba15(clut[clut_index])[idx]
    if bpp == 1:
        return rgba15(clut[clut_index])[raw]
    if bpp == 2:
        return rgba15(raw.view("<u2"))
    rgb = raw.reshape(h, -1)[:, : (w * 2 // 3) * 3].reshape(h, -1, 3)
    return np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=-1)
