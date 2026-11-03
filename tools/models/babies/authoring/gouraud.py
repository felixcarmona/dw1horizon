"""gouraud.py OUT.png NAME [NAME...] [--pitch 10] [--size 300]: renders like the PS1 game does (per-vertex lighting from
the TMD's own normals, interpolated; texture through each face's CLUT), front / 3-4 / side, plus a game-camera view.
Shows what the in-game look is, unlike animstudio's flat per-triangle shading."""
import sys, os, math, argparse
import numpy as np
from lib import mmd, OUT
DONOR = {'Pabumon': 15, 'Pichimon': 2, 'YukimiBotamon': 1, 'Nyokimon': 43, 'Motimon': 2, 'Bukamon': 2, 'Nyaromon': 30,
         'Yokomon': 44}
LIGHT = np.array([0.35, -0.75, 0.55]); LIGHT /= np.linalg.norm(LIGHT)   # from above, front-left (y negative = up)


def rot(yaw, pitch):
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rx @ Ry


def render(name, yaw_deg, pitch_deg, size):
    t = DONOR[name]
    m = mmd.MMD.load(f'{OUT}/{name}.MMD', t)
    tim = mmd.Tim4(open(f'{OUT}/{name}.TIM', 'rb').read())
    pal = np.array([[mmd.c15_to_rgba(c) for c in row] for row in tim.pal], np.float32)
    idx = np.frombuffer(bytes(tim.idx), np.uint8).reshape(tim.h, tim.w)
    nb = mmd.exe().bone_count[t]
    a = m.anims.anims[m.anims.table[0]]
    frames, _ = mmd.simulate(a, nb)
    pose = frames[0]; pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    mats = mmd.bone_matrices(m, pose)
    tris = []
    for b, (oi, _) in enumerate(mmd.exe().skeleton[t]):
        if oi < 0: continue
        M = np.array(mats[b], float); R = M[:3, :3]
        Rn = R / np.maximum(np.linalg.norm(R, axis=0), 1e-9)
        V = np.array([v[:3] for v in m.tmd.obj_verts(oi)], float) @ R.T + M[:3, 3]
        N = np.array([v[:3] for v in m.tmd.obj_norms(oi)], float) / 4096.0
        N = N @ Rn.T
        for p in m.tmd.objects[oi].prims:
            d = p.decode(); ids = d['verts']; ns = d['norms']
            if not d['uv']: continue
            row = (d['cba'] >> 6) - 488
            for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else []):
                nn = [N[ns[k] if len(ns) == len(ids) else ns[0]] for k in c] if ns else [None] * 3
                tris.append((V[[ids[k] for k in c]], [d['uv'][k] for k in c], nn, row, d['flag']))
    Rc = rot(math.radians(yaw_deg), math.radians(pitch_deg))
    allv = np.concatenate([tv[0] for tv in tris]) @ Rc.T
    mn, mx = allv.min(0), allv.max(0)
    sc = (size * 0.86) / max(mx[0] - mn[0], mx[1] - mn[1])
    ox, oy = size / 2 - (mn[0] + mx[0]) / 2 * sc, size / 2 - (mn[1] + mx[1]) / 2 * sc
    img = np.zeros((size, size, 3), np.float32) + (34, 38, 46)
    zb = np.full((size, size), 1e30)
    for V, uv, nn, row, flag in tris:
        P = V @ Rc.T
        S = np.c_[P[:, 0] * sc + ox, P[:, 1] * sc + oy, P[:, 2]]
        area = (S[1, 0] - S[0, 0]) * (S[2, 1] - S[0, 1]) - (S[1, 1] - S[0, 1]) * (S[2, 0] - S[0, 0])
        if abs(area) < 1e-9 or (area < 0 and not flag & 2): continue      # back-face cull like the game
        x0, x1 = max(0, int(S[:, 0].min())), min(size - 1, int(S[:, 0].max()) + 1)
        y0, y1 = max(0, int(S[:, 1].min())), min(size - 1, int(S[:, 1].max()) + 1)
        if x1 < x0 or y1 < y0: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        w0 = ((S[1, 0] - X) * (S[2, 1] - Y) - (S[1, 1] - Y) * (S[2, 0] - X)) / area
        w1 = ((S[2, 0] - X) * (S[0, 1] - Y) - (S[2, 1] - Y) * (S[0, 0] - X)) / area
        w2 = 1 - w0 - w1
        ins = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not ins.any(): continue
        z = w0 * S[0, 2] + w1 * S[1, 2] + w2 * S[2, 2]
        zsub = zb[y0:y1 + 1, x0:x1 + 1]
        ok = ins & (z < zsub)
        if not ok.any(): continue
        u = np.clip((w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0]).astype(int), 0, tim.w - 1)
        v = np.clip((w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1]).astype(int), 0, tim.h - 1)
        col = pal[min(row, len(pal) - 1)][idx[v, u]]
        ok &= col[..., 3] > 0
        if nn[0] is not None:
            lv = [0.62 + 0.55 * max(0.0, float(np.dot(n / (np.linalg.norm(n) or 1), -LIGHT))) for n in nn]
            lit = w0 * lv[0] + w1 * lv[1] + w2 * lv[2]
        else:
            lit = np.ones_like(w0)
        rgb = np.clip(col[..., :3] * lit[..., None], 0, 255)
        sub = img[y0:y1 + 1, x0:x1 + 1]
        sub[ok] = rgb[ok]; zsub[ok] = z[ok]
    return img.astype(np.uint8)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('names', nargs='+')
    ap.add_argument('--size', type=int, default=300); a = ap.parse_args()
    import cv2
    views = [(0, 8), (40, 14), (90, 8), (25, 40)]
    rows = [np.concatenate([render(n, y, p, a.size) for y, p in views], 1) for n in a.names]
    img = np.ascontiguousarray(np.concatenate(rows, 0))
    cv2.imwrite(a.out, cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA if img.shape[2] == 4 else cv2.COLOR_RGB2BGR)); print(a.out)
