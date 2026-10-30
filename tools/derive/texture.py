"""Byte-oriented PS1 texture unpacking shared by the disc readers."""
from .arraymath import Array, uint8

_NIBBLES = tuple(bytes((b & 15, b >> 4)) for b in range(256))


def indices4(raw, height, width):
    """Packed bytes -> height x width palette indices, low nibble first."""
    return Array(bytearray(b''.join(_NIBBLES[b] for b in raw)), (height, width), uint8)


def rgba15(colours, replicate=False):
    """PS1 colours -> RGBA, with either bit replication or floor(255*c/31)."""
    if replicate:
        expand = tuple((c << 3) | (c >> 2) for c in range(32))
    else:
        expand = tuple(c * 255 // 31 for c in range(32))
    data = bytearray()
    for c in colours.flat:
        data.extend((expand[c & 31], expand[c >> 5 & 31], expand[c >> 10 & 31], 255 if c else 0))
    return Array(data, colours.shape + (4,), uint8)
