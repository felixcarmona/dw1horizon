#!/usr/bin/env python3
"""background_check.py RAW TFS W H: per captured frame, how much of the screen matches the map background
at the camera offset (searched between the previous and current tick camera). Writes RAW.bg."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, array, random
raw, tfs, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
d = open(tfs, 'rb').read()
n = struct.unpack_from('<I', d, 4)[0]
clut = struct.unpack_from('<256H', d, 8)
BW, BH = W * 128, H * 128
bg = array.array('H', [0xFFFF]) * (BW * BH)
k = 0
mt = None
for ty in range(H):
    for tx in range(W):
        off = 8 + 512 * n + k * 0x4004 + 4; k += 1
        for y in range(128):
            row = d[off + y * 128: off + y * 128 + 128]
            base = (ty * 128 + y) * BW + tx * 128
            for x in range(128):
                bg[base + x] = clut[row[x]] & 0x7FFF
fr = open(raw, 'rb').read(); N = len(fr) // 153600
ex = [list(map(int, l.split())) for l in open(raw + '.extra').read().split('\n') if l.strip()]
random.seed(1)
pts = [(random.randrange(320), random.randrange(240)) for _ in range(600)]
def score(f, ox, oy):
    m = t = 0
    for x, y in pts:
        bx, by = x + ox, y + oy
        if 0 <= bx < BW and 0 <= by < BH:
            t += 1
            if (f[y * 320 + x] & 0x7FFF) == bg[by * BW + bx]: m += 1
    return m / max(t, 1)
# constant offset between camera and screen: search on frame 0
REF = int(__import__('os').environ.get('BG_REF', '0'))
f0 = array.array('H'); f0.frombytes(fr[REF * 153600:(REF + 1) * 153600])
cx, cy = ex[REF][0], ex[REF][1]
best = max(((score(f0, cx + dx, cy + dy), dx, dy) for dx in range(-40, 41) for dy in range(-40, 41)))
print('frame 0 offset', best)
_, DX, DY = best
out = []
pts_s = pts[:150]
def score_s(f, ox, oy):
    m = t = 0
    for x, y in pts_s:
        bx, by = x + ox, y + oy
        if 0 <= bx < BW and 0 <= by < BH:
            t += 1
            if (f[y * 320 + x] & 0x7FFF) == bg[by * BW + bx]: m += 1
    return m / max(t, 1)
last = (ex[0][0] + DX, ex[0][1] + DY)
for i in range(N):
    f = array.array('H'); f.frombytes(fr[i * 153600:(i + 1) * 153600])
    cur = (ex[i][0] + DX, ex[i][1] + DY)
    cands = {(last[0] + dx, last[1] + dy) for dx in range(-6, 7) for dy in range(-6, 7)}
    cands |= {(cur[0] + dx, cur[1] + dy) for dx in range(-3, 4) for dy in range(-3, 4)}
    s0, ox, oy = max((score_s(f, ox, oy), ox, oy) for ox, oy in cands)
    s = score(f, ox, oy)
    last = (ox, oy)
    out.append((i, s, ox, oy, ex[i][2] & 0xFF, ex[i][3] & 0xFF))
open(raw + '.bg', 'w').write('\n'.join(' '.join(map(str, o)) for o in out))
ss = sorted(out, key=lambda o: o[1])
print('worst frames (index, match, offset, window):', [(o[0], round(o[1], 3), o[2], o[3], o[4], o[5]) for o in ss[:12]])
import statistics
print('median match', round(statistics.median(o[1] for o in out), 3))
# per background tile: the visible part of each tile must match (a black or wrong tile scores ~0)
flag = []
low = []
worst_tile = 1.0
for (i, s, ox, oy, wx, wy) in out:
    f = array.array('H'); f.frombytes(fr[i * 153600:(i + 1) * 153600])
    stats = {}
    for y in range(0, 240, 3):
        by = y + oy
        if not 0 <= by < BH: continue
        for x in range(0, 320, 3):
            bx = x + ox
            if not 0 <= bx < BW: continue
            t = (bx // 64, by // 64)
            m, c = stats.get(t, (0, 0))
            stats[t] = (m + ((f[y * 320 + x] & 0x7FFF) == bg[by * BW + bx]), c + 1)
    for t, (m, c) in stats.items():
        if c >= 300:
            worst_tile = min(worst_tile, m / c)
            if m / c < 0.2: flag.append((i, t, round(m / c, 2), c))
            if m / c < 0.3: low.append((round(m / c, 3), i, t, ox, oy))
print('lowest per-tile match over all frames:', round(worst_tile, 3))
print('tiles under 20% match:', len(flag), 'in frames', sorted(set(f[0] for f in flag))[:5], '...', sorted(set(f[0] for f in flag))[-5:], len(set(f[0] for f in flag)), 'frames')
print('lowest cells', sorted(low)[:6])
