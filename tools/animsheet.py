#!/usr/bin/env python3
"""Contact sheets of MMD animations: one row per slot, N frames across, fixed camera.

`mmd.py preview` renders one pose and refits the view to it, so a hop or a lean looks the
same as the rest pose. This renders every frame with the same camera (fitted once to the
rest pose with a margin), with the entity's root motion and facing applied, so walk cycles,
hops and lunges can be judged before going to the emulator.

Usage (from the repository root):
  python3 tools/animsheet.py MMD OUT.png [--type T] [--slots 0 2 0x2e ...] [--frames 8]
         [--size 96] [--yaw 30] [--pitch 10] [--alltim F] [--tex-type T] [--margin 1.5]
         [--ticks 0 4 8 ...]      explicit ticks instead of N evenly spaced ones
         [--every K]              one frame every K ticks (all of the slot)
Without --slots: every slot the table uses, in slot order. Each row starts with a column
that encodes the slot number as a little bar code (bit 0 at the top); `--list` prints the
row -> slot order, the length in ticks, the loop sample and the root motion of each row.

Standard library only (uses tools/mmd.py).
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd  # noqa: E402

BG = (40, 44, 52)


def world_tris(m, pose, skel):
    mats = mmd.bone_matrices(m, pose)
    tris = []
    for b, (oi, _) in enumerate(skel):
        if oi < 0:
            continue
        M = mats[b]
        wv = []
        for x, y, z, _ in m.tmd.obj_verts(oi):
            wv.append((M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3],
                       M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3],
                       M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3]))
        for p in m.tmd.objects[oi].prims:
            d = p.decode()
            ids = d['verts']
            corners = [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else [])
            for c in corners:
                tris.append(([wv[ids[k]] for k in c], [d['uv'][k] for k in c] if d['uv'] else None, d))
    return tris


class Camera:
    def __init__(self, yaw, pitch):
        self.cy, self.sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        self.cp, self.sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def view(self, v):
        x, y, z = v
        x, z = self.cy * x + self.sy * z, -self.sy * x + self.cy * z
        y, z = self.cp * y - self.sp * z, self.sp * y + self.cp * z
        return x, y, z


def raster(tris, cam, tim, size, sc, ox, oy, img, x_off, W):
    zb = {}
    for pts, uv, d in tris:
        V = [cam.view(v) for v in pts]
        P = [(v[0] * sc + ox, v[1] * sc + oy, v[2]) for v in V]
        ux, uy, uz = (V[1][i] - V[0][i] for i in range(3))
        vx, vy, vz = (V[2][i] - V[0][i] for i in range(3))
        nz = ux * vy - uy * vx
        nl = math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + nz ** 2) or 1
        shade = 0.55 + 0.45 * abs(nz / nl)
        x0, x1 = max(0, int(min(p[0] for p in P))), min(size - 1, int(max(p[0] for p in P)) + 1)
        y0, y1 = max(0, int(min(p[1] for p in P))), min(size - 1, int(max(p[1] for p in P)) + 1)
        area = (P[1][0] - P[0][0]) * (P[2][1] - P[0][1]) - (P[1][1] - P[0][1]) * (P[2][0] - P[0][0])
        if abs(area) < 1e-9:
            continue
        row = ((d['cba'] >> 6) - 488) if d['cba'] else 0
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px, py = x + .5, y + .5
                w0 = ((P[1][0] - px) * (P[2][1] - py) - (P[1][1] - py) * (P[2][0] - px)) / area
                w1 = ((P[2][0] - px) * (P[0][1] - py) - (P[2][1] - py) * (P[0][0] - px)) / area
                w2 = 1 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = w0 * P[0][2] + w1 * P[1][2] + w2 * P[2][2]
                k = y * size + x
                if z >= zb.get(k, 1e30):
                    continue
                if uv and tim is not None:
                    u = int(w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0])
                    v = int(w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1])
                    u, v = max(0, min(tim.w - 1, u)), max(0, min(tim.h - 1, v))
                    c = tim.pal[min(row, tim.ch - 1)][tim.idx[v * tim.w + u]]
                    if c == 0:
                        continue
                    r, g, b, _ = mmd.c15_to_rgba(c)
                elif d['colors']:
                    r, g, b = d['colors'][0][:3]
                else:
                    r, g, b = 200, 200, 200
                zb[k] = z
                i = 4 * (y * W + x_off + x)
                img[i:i + 4] = bytes((int(r * shade), int(g * shade), int(b * shade), 255))


def slot_frames(m, nb, slot, max_ticks=600):
    """Poses per tick (bone 0 with its rotation and the accumulated root motion)."""
    a = m.anims.anims[m.anims.table[slot]]
    p = mmd.AnimPlayer(a, nb, slot)
    out = []
    while len(out) < max_ticks and p.tick(stop_at_infinite_loop=True):
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(p.root)
        out.append(snap)
    return out, p.loop_sample(), [(k, kind, c) for k, kind, c in p.events]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd')
    ap.add_argument('out')
    ap.add_argument('--type', type=lambda s: int(s, 0))
    ap.add_argument('--slots', nargs='*', type=lambda s: int(s, 0))
    ap.add_argument('--frames', type=int, default=8)
    ap.add_argument('--ticks', nargs='*', type=int)
    ap.add_argument('--every', type=int)
    ap.add_argument('--size', type=int, default=96)
    ap.add_argument('--yaw', type=float, default=30)
    ap.add_argument('--pitch', type=float, default=10)
    ap.add_argument('--margin', type=float, default=1.5)
    ap.add_argument('--alltim', default=os.path.join(mmd.EXTRACTED, 'CHDAT', 'ALLTIM.TIM'))
    ap.add_argument('--tex-type', type=lambda s: int(s, 0))
    ap.add_argument('--no-root', action='store_true', help='ignore root motion (keep the model centred)')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    m = mmd.MMD.load(a.mmd, a.type)
    e = mmd.exe()
    nb, skel = e.bone_count[m.type], e.skeleton[m.type]
    tim = mmd.load_tim(a.alltim, a.tex_type if a.tex_type is not None else m.type)
    slots = a.slots if a.slots else [s for s, i in enumerate(m.anims.table) if i is not None]
    cam = Camera(a.yaw, a.pitch)

    rest, _, _ = slot_frames(m, nb, 0)
    pose0 = rest[0]
    pose0[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    pts = [cam.view(v) for t in world_tris(m, pose0, skel) for v in t[0]]
    mnx, mxx = min(p[0] for p in pts), max(p[0] for p in pts)
    mny, mxy = min(p[1] for p in pts), max(p[1] for p in pts)
    span = max(mxx - mnx, mxy - mny) * a.margin
    S = a.size
    sc = S / span
    ox = S / 2 - (mnx + mxx) / 2 * sc
    oy = S / 2 - (mny + mxy) / 2 * sc + (span - (mxy - mny)) * sc * 0.25

    rows = []
    for s in slots:
        fr, ls, ev = slot_frames(m, nb, s)
        if a.ticks:
            ticks = [t for t in a.ticks if t < len(fr)]
        elif a.every:
            ticks = list(range(0, len(fr), a.every))
        else:
            n = a.frames
            ticks = sorted(set(round(i * (len(fr) - 1) / max(1, n - 1)) for i in range(n)))
        rows.append((s, fr, ticks, ls, ev))
        if a.list:
            snd = [(k, c['bank'], c['note']) for k, kind, c in ev if kind == 'sound']
            print(f'row {len(rows) - 1}: slot {s:#04x}  {len(fr)} ticks  loop {ls}  root '
                  f'{[round(x) for x in fr[-1][0][6:9]]}  ticks {ticks}  sounds {snd}')
    cols = max(len(r[2]) for r in rows)
    LAB = 6
    W, H = LAB + cols * S, len(rows) * S
    img = bytearray(bytes((*BG, 255)) * (W * H))
    for ri, (s, fr, ticks, ls, ev) in enumerate(rows):
        sub = bytearray(bytes((*BG, 255)) * (W * S))
        for bit in range(8):                       # slot bar code
            if s >> bit & 1:
                for y in range(bit * S // 8 + 1, (bit + 1) * S // 8 - 1):
                    for x in range(1, LAB - 1):
                        sub[4 * (y * W + x):4 * (y * W + x) + 4] = bytes((230, 200, 60, 255))
        for ci, t in enumerate(ticks):
            pose = [list(v) for v in fr[t]]
            if a.no_root:
                pose[0] = [4096, 4096, 4096] + pose[0][3:6] + [0, 0, 0]
            else:
                pose[0] = pose[0][:6] + [round(x) for x in pose[0][6:9]]
            # ground line
            gy = cam.view((0, 0, 0))[1] * sc + oy
            if 0 <= gy < S:
                for x in range(S):
                    i = 4 * (int(gy) * W + LAB + ci * S + x)
                    sub[i:i + 4] = bytes((70, 76, 90, 255))
            raster(world_tris(m, pose, skel), cam, tim, S, sc, ox, oy, sub, LAB + ci * S, W)
            for y in range(S):                       # cell border
                i = 4 * (y * W + LAB + ci * S)
                sub[i:i + 4] = bytes((20, 22, 26, 255))
        img[4 * W * S * ri:4 * W * S * (ri + 1)] = sub
    mmd.png_write(a.out, W, H, img)
    print(f'{a.out}: {len(rows)} rows x {cols} frames ({W}x{H})')


if __name__ == '__main__':
    main()
