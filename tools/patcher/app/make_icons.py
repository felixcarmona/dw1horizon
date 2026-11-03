#!/usr/bin/env python3
"""The desktop patcher's icon: web/favicon.svg (a sunrise over the horizon on a soft sky), drawn without libraries.

    python3 tools/patcher/app/make_icons.py OUT_FOLDER     # icon.png (512), icon.ico (16-256), icon.icns (16-1024)

gui.py draws the window's icon with png() at run time; the build (tools/patcher/app/build.py) writes the files the
Windows .exe and the macOS .app carry. Standard library only.
"""
import os
import struct
import sys
import zlib

# web/favicon.svg, in its 32-unit box
STOPS = [(0.0, (0xcf, 0xd8, 0xf6)), (0.55, (0xf3, 0xd3, 0xe0)), (1.0, (0xff, 0xe1, 0xc4))]
SUN, BAR = (0xf0, 0x7a, 0x3a), (0x1b, 0x1a, 0x24)


def _sky(y):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if y <= b:
            t = (y - a) / (b - a)
            return tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3))
    return STOPS[-1][1]


def _rounded(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r); cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _sample(x, y):
    """(r, g, b, a) at a point of the 32-unit box."""
    if not _rounded(x, y, 0, 0, 32, 32, 8):
        return None
    if _rounded(x, y, 5, 21.5, 27, 23.5, 1):
        return BAR
    if y <= 20 and (x - 16) ** 2 + (y - 20) ** 2 <= 49:
        return SUN
    return _sky(y / 32)


def pixels(size):
    """RGBA bytes, size x size, supersampled."""
    ss = 4 if size <= 64 else 2 if size <= 256 else 1
    out = bytearray()
    step = 32 / (size * ss)
    for py in range(size):
        for px in range(size):
            acc, n = [0.0, 0.0, 0.0], 0
            for sy in range(ss):
                for sx in range(ss):
                    c = _sample((px * ss + sx + 0.5) * step, (py * ss + sy + 0.5) * step)
                    if c is not None:
                        n += 1
                        for i in range(3): acc[i] += c[i]
            if n:
                out += bytes(int(acc[i] / n + 0.5) for i in range(3)) + bytes([int(255 * n / (ss * ss) + 0.5)])
            else:
                out += b'\0\0\0\0'
    return bytes(out)


def png(size):
    raw = pixels(size)
    rows = b''.join(b'\0' + raw[y * size * 4:(y + 1) * size * 4] for y in range(size))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def ico(sizes=(16, 24, 32, 48, 64, 128, 256)):
    """PNG-compressed entries (Windows Vista and later)."""
    images = [png(s) for s in sizes]
    head = struct.pack('<HHH', 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b''
    for s, data in zip(sizes, images):
        entries += struct.pack('<BBBBHHII', s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + entries + b''.join(images)


def icns():
    """PNG entries: 16, 32, 64 (32@2x), 128, 256, 512, 1024 (512@2x)."""
    kinds = [(b'icp4', 16), (b'icp5', 32), (b'icp6', 64), (b'ic07', 128), (b'ic08', 256), (b'ic09', 512),
             (b'ic10', 1024), (b'ic11', 32), (b'ic12', 64), (b'ic13', 256), (b'ic14', 512)]
    cache = {}
    body = b''
    for kind, s in kinds:
        data = cache.setdefault(s, png(s))
        body += kind + struct.pack('>I', len(data) + 8) + data
    return b'icns' + struct.pack('>I', len(body) + 8) + body


def main(argv):
    out = argv[0] if argv else '.'
    os.makedirs(out, exist_ok=True)
    for name, data in (('icon.png', png(512)), ('icon.ico', ico()), ('icon.icns', icns())):
        with open(os.path.join(out, name), 'wb') as f:
            f.write(data)
        print(os.path.join(out, name), len(data))


if __name__ == '__main__':
    main(sys.argv[1:])
