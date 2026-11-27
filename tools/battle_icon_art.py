#!/usr/bin/env python3
"""Battle command icons of the five new technique rows in unused BTLCOMND texels of ETCTIM.BIN.

The command ring of a fight shows each technique with its element's icon from BTLCOMND (entry 1, VRAM 960,448,
256x64, texture page 960,256). The original atlas has seven element icons; the rows of Darkness, Light, Water,
Weapon and Earth (elements 7..11) draw their Techset tiles here (content/localized/techniques/icons*.txt, the
10x10 drawings without the grey Techset tile, three of their rows and columns doubled to 13x13 so that they stand as
tall as the original icons) and use the Techset's own palettes in SYSTEM_W
(tools/localize/tech_rows_art.py), so both screens always show the same icon.

A command icon is a 16x15 window and the chosen one blinks: the engine moves the window 16 texels right on every
other beat. Darkness, Light and Water have two tiles on the Techset (large, small), so each gets a 32x15 pair.
Weapon and Earth have one tile and blink with their second palette, as on the Techset; the C side swaps the
CLUT instead of moving the window (TECH_ROW_BATTLE_* in include/dw/tech_row_icons.h, same numbers).

Every texel of a window that is not drawing is CLUT index 15, which is 0 (transparent) in the Techset palettes;
the atlas' own empty texels are index 0, an opaque colour there. A window takes only texels that are empty after
the field HUD and care-bubble art, and fails closed otherwise.
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.localize.build import tim_entries
from tools.localize import tech_rows_art

PATH = 'ETCDAT/ETCTIM.BIN'
ENTRY = 1
ATLAS_V = 0xc0                  # BTLCOMND's first row in its texture page
WINDOW = (16, 15)               # the engine's command icon window (setUVWH 0x10, 0xf)
OFFSET = (2, 1)                 # where the 13x13 drawing sits in a window
DOUBLED = (2, 5, 7)             # the drawing's rows and columns drawn twice
CLEAR = 15                      # transparent in both Techset palettes
# atlas (u, v) of each new element's window, Darkness to Earth; v without ATLAS_V
CELLS = ((223, 27), (200, 46), (83, 48), (115, 48), (232, 46))
PAIRS = 3                       # Darkness, Light and Water have a blink tile 16 texels right
CLUTS = (tech_rows_art.CLUT_ID,) * 3 + (tech_rows_art.NEW_CLUT_IDS[0],) * 2
BLINK_CLUT = tech_rows_art.NEW_CLUT_IDS[1]


def uvs():
    """-> the texture page (u, v) of each new element's icon, as the C tables hold them"""
    return tuple((u, v + ATLAS_V) for u, v in CELLS)


def windows():
    """-> (u, v, w, h) in the atlas of each element's whole window, its blink tile included"""
    w, h = WINDOW
    return tuple((u, v, w * (2 if i < PAIRS else 1), h) for i, (u, v) in enumerate(CELLS))


def drawings():
    """-> [[tile, ...] per element] as 13 rows of 13 SYSTEM_W indices, the grey tile made CLEAR"""
    _, pairs = tech_rows_art.art()
    _, singles = tech_rows_art.new_art()
    grey = 12

    index = [1 + i for i in range(10) for _ in range(2 if i in DOUBLED else 1)]

    def inner(tile):
        return [[CLEAR if tile[y][x] == grey else tile[y][x] for x in index] for y in index]
    return [[inner(t) for t in pair] for pair in pairs] + [[inner(t)] for t in singles]


def build(data):
    """Return an ETCTIM copy with the five icons; reject occupied texels or an unexpected allocation."""
    d = bytearray(data)
    dst, bpp, w, h = tim_entries(d)[ENTRY]
    if (bpp, w, h) != (0, 256, 64) or struct.unpack_from('<4H', d, dst - 8) != (960, 448, 64, 64):
        raise ValueError('unexpected BTLCOMND allocation')

    def pixel(x, y):
        return (d[dst + y * 128 + x // 2] >> (4 * (x & 1))) & 15

    def put(x, y, n):
        p = dst + y * 128 + x // 2
        shift = 4 * (x & 1)
        d[p] = (d[p] & ~(15 << shift)) | n << shift

    for u, v, ww, wh in windows():
        if u + ww > 256 or v + ATLAS_V + wh > 255:
            raise ValueError(f'battle icon window past its texture page: {u},{v}')
        if any(pixel(x, y) for y in range(v, v + wh) for x in range(u, u + ww)):
            raise ValueError(f'battle icon cell is occupied: {u},{v}')
    for (u, v, ww, wh), tiles in zip(windows(), drawings()):
        for y in range(v, v + wh):
            for x in range(u, u + ww):
                put(x, y, CLEAR)
        for k, tile in enumerate(tiles):
            for y, row in enumerate(tile):
                for x, n in enumerate(row):
                    put(u + k * WINDOW[0] + OFFSET[0] + x, v + OFFSET[1] + y, n)
    return bytes(d)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('out', type=Path)
    p.add_argument('--extracted', type=Path, default=Path(__file__).resolve().parents[1] / 'extracted')
    a = p.parse_args()
    out = a.out / PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build((a.extracted / PATH).read_bytes()))
    print(out)


if __name__ == '__main__':
    main()
