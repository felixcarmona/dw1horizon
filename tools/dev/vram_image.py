#!/usr/bin/env python3
"""Converts a PS1 VRAM dump (1024×512, 16-bit BGR555, 1 MB; what PCSX-Redux's
/api/v1/gpu/vram/raw returns) to PNG.

Usage:  vram2png.py vram.bin output.png [X Y WIDTH HEIGHT]   (optional crop)
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import struct, sys, zlib

def main():
    v = open(sys.argv[1], 'rb').read(); W = 1024
    x0, y0, w, h = (int(a) for a in sys.argv[3:7]) if len(sys.argv) >= 7 else (0, 0, 1024, 512)
    rows = []
    for y in range(y0, y0 + h):
        px = struct.unpack_from(f'<{w}H', v, (y * W + x0) * 2); line = bytearray()
        for p in px: line += bytes(((p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3))
        rows.append(bytes(line))
    raw = b''.join(b'\0' + r for r in rows)
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(sys.argv[2], 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                                  + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))

if __name__ == '__main__':
    main()
