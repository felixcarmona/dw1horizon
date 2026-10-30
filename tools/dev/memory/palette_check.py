#!/usr/bin/env python3
"""palette_check.py: which TFS palette is in VRAM (0,480), and does the visible tile window match the TFS file."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, os
import membudget as mb
em = mb.Emu(); r = em.ram(); s = em.syms; v = em.vram()
row = lambda y, x0, n: v[(y * 1024 + x0) * 2:(y * 1024 + x0 + n) * 2]
hdr = 0x10000
n = struct.unpack_from('<I', r, hdr + 4)[0]
cl = [r[hdr + 8 + 512 * k: hdr + 8 + 512 * (k + 1)] for k in range(min(n, 5))]
act = row(480, 0, 256)
print('nCLUT', n, 'active =', [k for k in range(len(cl)) if cl[k] == act] or 'none (fading?)')
# tile window check against the file on disc
scr = mb.screen_id(mb.Ram(r, s))
name = mb.MAPS[scr]['file']
import glob
f = glob.glob(f'{_DEV_ROOT}/extracted/MAP/*/{name}.TFS')[0]
d = open(f, 'rb').read()
md = s['MAP_TILE_DATA'] - 0x80000000
W, H = r[md + 0x1bb8], r[md + 0x1bb9]
wx, wy = r[s['MAP_TILE_X'] - 0x80000000], r[s['MAP_TILE_Y'] - 0x80000000]
mt = struct.unpack_from('<35b', r, s['MAP_TILES'] - 0x80000000)
seq = {}; k = 0
for i in range(W * H):
    if mt[i] != -1: seq[i] = k; k += 1
bad = []
for y in range(wy, min(wy + 3, H)):
    for x in range(wx, min(wx + 4, W)):
        i = x + y * W
        if i not in seq: continue
        off = 8 + 512 * n + seq[i] * 0x4004 + 4
        want = d[off:off + 0x4000]
        vx, vy = 768 + 64 * (x % 4), 128 * (y % 3)
        got = b''.join(row(vy + j, vx, 64) for j in range(128))
        if got != want: bad.append((x, y))
print(f'{name} {W}x{H} window {wx},{wy}: tiles not matching the file: {bad or "none"}')
