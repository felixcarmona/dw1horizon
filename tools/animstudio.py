#!/usr/bin/env python3
"""Animation studio: see how a model animates, outside the game. Mesh, skeleton only, both over each other, the gait
curves of the feet, several models side by side (the donor's own walk next to the retargeted one), as a video or a sheet.

  animstudio.py video OUT.mp4 MODEL [MODEL ...] [--slot 2] [--panels mesh:side,skel:side,xray:front,gait] [--cycles 3]
                      [--speed 1] [--size 360]
  animstudio.py sheet OUT.png MODEL [MODEL ...] [--slot 2] [--panels ...] [--ticks 0 3 6 ...]
  animstudio.py metrics MODEL [MODEL ...] [--slot 2]   foot slip over the ground in stance, foot lift, root speed
  animstudio.py bones MODEL                 the hierarchy: parent, rest position, side, mesh part (extent, vertices)

MODEL is  FILE.MMD:TYPE[:TEXTURE[:SLOT[:LABEL]]]  where TEXTURE is a single-model .TIM (an import's NeoCrimson.TIM) or absent (the
disc's ALLTIM entry of TYPE: the original Digimon). One row of panels per model, the same slot for all (--slot, or
FILE:TYPE:TEX:SLOT as a fourth field).

Panels (kind:view): mesh, skel (bones as lines, the bone number at each joint; orange = right side x>0, cyan = left,
white = centre; bones under 100 units from the ground in red), xray (mesh faint + skeleton); views front, side, back,
three (3/4), top. gait: height of the two lowest bones and their position along the walking direction in the world
(root motion included): a planted foot is a flat line in the second curve, a sliding foot is a slope. The ground has
marks every 100 units that move with the root motion, so sliding is visible. The camera follows the root.
Runs under the card-game venv (numpy, OpenCV).
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, math, os, subprocess, sys, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
try:
    import numpy as np
    from tools.image import Image, ImageDraw
except ImportError:
    py = os.path.join(os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimoncardbattle')), '.venv', 'bin', 'python')
    if os.path.exists(py) and not os.environ.get('ANIMSTUDIO_REEXEC'):
        os.environ['ANIMSTUDIO_REEXEC'] = '1'
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    raise SystemExit('animstudio: needs numpy and OpenCV (the venv of the card-game project)')
sys.path.insert(0, HERE)
import mmd, animsheet  # noqa: E402

FFMPEG = os.path.expanduser('~/.local/bin/ffmpeg')
VIEWS = {'front': (0, 8), 'side': (90, 8), 'back': (180, 8), 'three': (40, 14), 'top': (0, 85)}
BG = (34, 38, 46)


class Model:
    def __init__(self, spec, slot):
        f = spec.split(':')
        self.path, self.type = f[0], int(f[1], 0)
        self.tex = f[2] if len(f) > 2 and f[2] else None
        self.slot = int(f[3], 0) if len(f) > 3 and f[3] else slot
        self.name = (f[4] if len(f) > 4 and f[4] else os.path.basename(os.path.dirname(os.path.abspath(self.path))) + '/' + os.path.basename(self.path))
        self.m = mmd.MMD.load(self.path, self.type)
        e = mmd.exe()
        self.nb, self.skel = e.bone_count[self.type], e.skeleton[self.type]
        if self.tex:
            self.tim = mmd.Tim4(open(self.tex, 'rb').read())
        else:
            self.tim = mmd.load_tim(os.path.join(mmd.EXTRACTED, 'CHDAT', 'ALLTIM.TIM'), self.type)
        self.pal = np.zeros((self.tim.ch, 16, 4), np.uint8)
        for r in range(self.tim.ch):
            for i, c in enumerate(self.tim.pal[r]):
                self.pal[r, i] = mmd.c15_to_rgba(c)
        self.idx = np.ascontiguousarray(np.frombuffer(bytes(self.tim.idx), np.uint8).reshape(self.tim.h, self.tim.w))
        self.pal = np.ascontiguousarray(self.pal)
        self.fast = None
        self.frames, self.loop, _ = animsheet.slot_frames(self.m, self.nb, self.slot)
        rest, _, _ = animsheet.slot_frames(self.m, self.nb, 0)
        self.rest = [list(v) for v in rest[0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        mats = mmd.bone_matrices(self.m, self.rest)
        self.restpos = [(M[0][3], M[1][3], M[2][3]) for M in mats]
        ys = [p[1] for p in self.restpos[1:]]
        self.lowest = sorted(range(1, self.nb), key=lambda b: -self.restpos[b][1])
        pts = [v for t in animsheet.world_tris(self.m, self.rest, self.skel) for v in t[0]]
        a = np.array(pts)
        self.verts = a
        self.extent = float(max(a[:, 1].max() - a[:, 1].min(), a[:, 0].ptp() if hasattr(a, 'ptp') else np.ptp(a[:, 0]), 1))
        self.center_y = float((a[:, 1].max() + a[:, 1].min()) / 2)

    def set_slot(self, slot):
        """Play another slot of the same model (a batch renders every animation without loading the model again)."""
        self.slot = slot
        self.frames, self.loop, _ = animsheet.slot_frames(self.m, self.nb, slot)

    def pose(self, t):
        p = [list(v) for v in self.frames[t]]
        root = p[0][6:9]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]     # the model stays at the origin, the ground moves
        return p, root


def tris_by_bone(m, pose, skel):
    mats = mmd.bone_matrices(m, pose)
    out = []
    for b, (oi, _) in enumerate(skel):
        if oi < 0:
            continue
        M = mats[b]
        wv = [(M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3], M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3],
               M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3]) for x, y, z, _ in m.tmd.obj_verts(oi)]
        for p in m.tmd.objects[oi].prims:
            d = p.decode(); ids = d['verts']
            for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else []):
                out.append(([wv[ids[k]] for k in c], [d['uv'][k] for k in c] if d['uv'] else None, d, b))
    return out


def bone_color(b):
    import colorsys
    r, g, bl = colorsys.hsv_to_rgb((b * 0.381966) % 1.0, 0.65, 0.95)
    return (r * 255, g * 255, bl * 255)


def cam_xform(yaw, pitch):
    cy, sy, cp, sp = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def f(v):
        x, y, z = v
        x, z = cy * x + sy * z, -sy * x + cy * z
        y, z = cp * y - sp * z, sp * y + cp * z
        return x, y, z
    return f


_C = None


def _raster_lib():
    global _C
    if _C is None:
        import ctypes
        so = os.path.join(os.path.dirname(HERE), 'build', 'review', 'animraster.so')
        src = os.path.join(HERE, 'animraster.c')
        if not os.path.exists(so) or os.path.getmtime(so) < os.path.getmtime(src):
            os.makedirs(os.path.dirname(so), exist_ok=True)
            tmp = so + f'.{os.getpid()}'
            subprocess.run(['gcc', '-O2', '-shared', '-fPIC', src, '-o', tmp, '-lm'], check=True)
            os.replace(tmp, so)
        _C = ctypes.CDLL(so)
    return _C


class FastMesh:
    """The model's triangles as arrays, made once: per pose only the vertices move (numpy), the rasterizer is C."""

    def __init__(self, mod):
        m = mod.m
        verts, self.vb, tri, uv, row, flat, tex, bone = [], [], [], [], [], [], [], []
        self.slices = []                                    # (bone, first vertex, count)
        n = 0
        for b, (oi, _) in enumerate(mod.skel):
            if oi < 0:
                continue
            vs = m.tmd.obj_verts(oi)
            self.slices.append((b, n, len(vs)))
            verts += [v[:3] for v in vs]
            for p in m.tmd.objects[oi].prims:
                d = p.decode(); ids = d['verts']
                for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else []):
                    tri.append([n + ids[k] for k in c])
                    has = bool(d['uv'])
                    tex.append(1 if has else 0)
                    uv.append([x for k in c for x in (d['uv'][k] if has else (0, 0))])
                    row.append(((d['cba'] >> 6) - 488) if d['cba'] else 0)
                    flat.append(list(d['colors'][0][:3]) if d['colors'] else [200, 200, 200])
                    bone.append(b)
            n += len(vs)
        self.V = np.array(verts, np.float32).reshape(-1, 3)
        self.tri = np.array(tri, np.int32); self.uv = np.array(uv, np.int32); self.row = np.array(row, np.int32)
        self.flat = np.array(flat, np.uint8); self.tex = np.array(tex, np.uint8); self.bone = np.array(bone, np.int32)
        self.bcol = np.array([bone_color(b) for b in range(len(mod.skel))], np.uint8)

    def world(self, mats):
        out = np.empty_like(self.V)
        for b, a, k in self.slices:
            M = np.array(mats[b], np.float32)
            out[a:a + k] = self.V[a:a + k] @ M[:3, :3].T + M[:3, 3]
        return out


class Panel:
    def __init__(self, mod, kind, view, size):
        self.mod, self.kind, self.view, self.size = mod, kind, view, size
        yaw, pitch = VIEWS[view] if kind != 'gait' else (0, 0)
        self.cam = cam_xform(yaw, pitch)
        self.cam_params = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch)))
        vv = [self.cam(tuple(v)) for v in mod.verts[::7]]
        xs, ys = [v[0] for v in vv], [v[1] for v in vv]
        w, h = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
        self.sc = size / (max(w, h) * 1.3)
        self.ox = size / 2 - (min(xs) + max(xs)) / 2 * self.sc
        self.oy = size / 2
        self.gy = size * 0.9 - max(ys) * self.sc           # the lowest point of the rest mesh stands on the ground line

    def px(self, v):
        x, y, z = self.cam(v)
        sy = self.gy + y * self.sc if self.view != 'top' else self.size / 2 + y * self.sc
        if self.view == 'top':
            return self.ox + x * self.sc, self.size / 2 + z * self.sc
        return self.ox + x * self.sc, sy

    def ground(self, d, root):
        if self.view == 'top':
            return
        W = self.size
        d.line([(0, self.gy), (W, self.gy)], fill=(80, 88, 104))
        for k in range(-30, 31):               # marks along the walking direction (z) and across (x)
            for (pt0, pt1) in (((0, 0, k * 100 - root[2] % 100 - 0), (0, 0, k * 100 - root[2] % 100)),
                               ((k * 100 - root[0] % 100, 0, 0), (k * 100 - root[0] % 100, 0, 0))):
                x, y = self.px(pt0)
                if 0 <= x < W:
                    d.line([(x, self.gy - 3), (x, self.gy + 3)], fill=(120, 130, 150))

    def render(self, t):
        mod, S = self.mod, self.size
        pose, root = mod.pose(t)
        img = Image.new('RGB', (S, S), BG)
        d = ImageDraw.Draw(img)
        if self.kind in ('mesh', 'xray', 'parts'):
            self.mesh(img, pose, 0.30 if self.kind == 'xray' else 1.0)
            d = ImageDraw.Draw(img)
        self.ground(d, root)
        if self.kind in ('skel', 'xray', 'parts'):
            self.skeleton(d, pose)
        return img

    def mesh(self, img, pose, alpha):
        mod, S = self.mod, self.size
        if getattr(mod, 'fast', None) is None:
            mod.fast = FastMesh(mod)
        F = mod.fast
        W = F.world(mmd.bone_matrices(mod.m, pose))
        cy, sy, cp, sp = self.cam_params
        x = cy * W[:, 0] + sy * W[:, 2]; z = -sy * W[:, 0] + cy * W[:, 2]
        y = cp * W[:, 1] - sp * z; z = sp * W[:, 1] + cp * z
        if self.view == 'top':
            sx_, sy_, sz_ = self.ox + x * self.sc, S / 2 + z * self.sc, y
        else:
            sx_, sy_, sz_ = self.ox + x * self.sc, self.gy + y * self.sc, z
        scr = np.stack([sx_, sy_, sz_], 1).astype(np.float32)
        A = scr[F.tri]                                           # (T, 3, 3)
        ux, uy = A[:, 1, 0] - A[:, 0, 0], A[:, 1, 1] - A[:, 0, 1]
        vx, vy = A[:, 2, 0] - A[:, 0, 0], A[:, 2, 1] - A[:, 0, 1]
        cam = np.stack([x, y, z], 1)[F.tri]
        e1, e2 = cam[:, 1] - cam[:, 0], cam[:, 2] - cam[:, 0]
        nrm = np.cross(e1, e2); nl = np.linalg.norm(nrm, axis=1); nl[nl == 0] = 1
        shade = (0.55 + 0.45 * np.abs(nrm[:, 2] / nl)).astype(np.float32)
        P = np.ascontiguousarray(A.reshape(-1, 9), np.float32)
        zb = np.full(S * S, 1e30, np.float32); out = np.zeros(S * S * 3, np.uint8); hit = np.zeros(S * S, np.uint8)
        tex = F.tex if self.kind != 'parts' else np.zeros_like(F.tex)
        flat = F.flat if self.kind != 'parts' else F.bcol[F.bone]
        import ctypes as C
        ptr = lambda a, t: a.ctypes.data_as(C.POINTER(t))
        _raster_lib().raster(C.c_int(len(F.tri)), ptr(P, C.c_float), ptr(F.uv, C.c_int), ptr(F.row, C.c_int), ptr(shade, C.c_float),
                             ptr(np.ascontiguousarray(flat), C.c_ubyte), ptr(tex, C.c_ubyte), ptr(mod.pal, C.c_ubyte), C.c_int(mod.pal.shape[0]),
                             ptr(mod.idx, C.c_ubyte), C.c_int(mod.tim.w), C.c_int(mod.tim.h), C.c_int(S), C.c_int(S), ptr(zb, C.c_float),
                             ptr(out, C.c_ubyte), ptr(hit, C.c_ubyte))
        base = np.asarray(img, np.float32).reshape(-1, 3)
        col = out.reshape(-1, 3).astype(np.float32)
        res = np.where(hit[:, None] == 1, col * alpha + base * (1 - alpha), base)
        img.paste(Image.fromarray(res.reshape(S, S, 3).astype(np.uint8)))

    def skeleton(self, d, pose):
        mod = self.mod
        mats = mmd.bone_matrices(mod.m, pose)
        pos = [(M[0][3], M[1][3], M[2][3]) for M in mats]
        low = set(mod.lowest[:2])
        for b in range(1, mod.nb):
            par = mod.skel[b][1]
            if par < 1:
                continue
            side = mod.restpos[b][0]
            c = (255, 160, 50) if side > 25 else (80, 200, 235) if side < -25 else (235, 235, 235)
            if b in low:
                c = (255, 70, 70)
            d.line([self.px(pos[par]), self.px(pos[b])], fill=c, width=2)
        for b in range(1, mod.nb):
            x, y = self.px(pos[b])
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255))
            d.text((x + 3, y - 5), str(b), fill=(255, 235, 120))


def gait(mod, size, t, curves):
    img = Image.new('RGB', (size, size), BG); d = ImageDraw.Draw(img)
    n = len(mod.frames)
    d.text((6, 4), 'foot height (up)', fill=(230, 230, 230)); d.text((6, size // 2 + 2), 'foot z in the world (flat = planted)', fill=(230, 230, 230))
    for k, (b, hs, zs) in enumerate(curves):
        col = (255, 70, 70) if k == 0 else (255, 160, 50)
        for series, (y0, y1) in ((hs, (size // 2 - 8, 22)), (zs, (size - 8, size // 2 + 20))):
            lo, hi = min(series), max(series)
            pts = [(8 + i * (size - 16) / max(1, n - 1), y0 + (v - lo) / ((hi - lo) or 1) * (y1 - y0)) for i, v in enumerate(series)]
            d.line(pts, fill=col, width=2)
        d.text((size - 40, 18 + 12 * k), f'bone {b}', fill=col)
    x = 8 + t * (size - 16) / max(1, n - 1)
    d.line([(x, 14), (x, size - 4)], fill=(255, 255, 255))
    return img


def gait_curves(mod):
    out = []
    for b in mod.lowest[:2]:
        hs, zs = [], []
        for t in range(len(mod.frames)):
            pose, root = mod.pose(t)
            M = mmd.bone_matrices(mod.m, pose)[b]
            hs.append(-M[1][3]); zs.append(M[2][3] + root[2])
        out.append((b, hs, zs))
    return out


def build(models, panels, size):
    rows = []
    for mod in models:
        ps = []
        for spec in panels:
            kind, _, view = spec.partition(':')
            ps.append((kind, Panel(mod, kind, view or 'side', size) if kind != 'gait' else None))
        rows.append((mod, ps, gait_curves(mod) if any(k == 'gait' for k, _ in ps) else None))
    return rows


def frame(rows, t, size, label_h=18):
    W = size * max(len(r[1]) for r in rows)
    out = Image.new('RGB', (W, (size + label_h) * len(rows)), (20, 22, 26))
    for ri, (mod, ps, curves) in enumerate(rows):
        tt = t % len(mod.frames)
        d = ImageDraw.Draw(out)
        d.text((6, ri * (size + label_h) + 3), f'{mod.name}   slot {mod.slot:#x}  tick {tt}/{len(mod.frames)}' if len(mod.name) > 24 else f'{mod.name}  type {mod.type}  slot {mod.slot:#x}  tick {tt}/{len(mod.frames)}', fill=(255, 255, 255))
        for ci, (kind, p) in enumerate(ps):
            im = gait(mod, size, tt, curves) if kind == 'gait' else p.render(tt)
            out.paste(im, (ci * size, ri * (size + label_h) + label_h))
    return out


def metrics(mod):
    """Per foot: stance ticks (foot near its lowest height), and the slip = the foot's speed over the ground during
    stance as a percentage of the root's speed (0 = planted, 100 = the foot moves with the body, negative = backwards)."""
    n = len(mod.frames)
    roots = [mod.pose(t)[1][2] for t in range(n)]
    rs = (roots[-1] - roots[0]) / max(1, n - 1)                   # root speed per tick (z, negative = forward)
    res = []
    for b in mod.lowest[:2]:
        ys, zs = [], []
        for t in range(n):
            pose, root = mod.pose(t)
            M = mmd.bone_matrices(mod.m, pose)[b]
            ys.append(M[1][3]); zs.append(M[2][3] + root[2])
        lo, hi = max(ys), min(ys)                                   # y down: the largest y is the lowest point
        stance = [t for t in range(n - 1) if ys[t] > lo - 0.25 * (lo - hi)]
        slip = [abs(zs[t + 1] - zs[t]) / abs(rs) * 100 for t in stance] if rs else []
        lift = lo - hi
        res.append((b, len(stance), n, (sum(slip) / len(slip)) if slip else 0, max(map(abs, slip), default=0), lift))
    return rs, res


def cmd_metrics(a):
    for spec in a.models:
        mod = Model(spec, a.slot)
        rs, res = metrics(mod)
        print(f'{mod.name} slot {mod.slot:#x}: {len(mod.frames)} ticks, root speed {rs:.1f}/tick')
        for b, ns, n, mean, worst, lift in res:
            print(f'   foot {b}: stance {ns}/{n} ticks, slip mean {mean:6.1f} % worst {worst:6.1f} % of the root speed, foot lift {lift:.0f}')


def cmd_bones(a):
    mod = Model(a.models[0], 0)
    mats = mmd.bone_matrices(mod.m, mod.rest)
    print(f'{mod.name}: {mod.nb} bones; bone: parent, object, rest position (x right+, y down+, z), side, mesh part')
    for b in range(mod.nb):
        oi, par = mod.skel[b]
        x, y, z = mod.restpos[b]
        part = ''
        if oi >= 0:
            vs = mod.m.tmd.obj_verts(oi)
            if vs:
                M = mats[b]
                w = [(M[0][0] * v[0] + M[0][1] * v[1] + M[0][2] * v[2] + M[0][3], M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2] + M[1][3],
                      M[2][0] * v[0] + M[2][1] * v[1] + M[2][2] * v[2] + M[2][3]) for v in vs]
                lo = [min(p[i] for p in w) for i in range(3)]; hi = [max(p[i] for p in w) for i in range(3)]
                part = f'{len(vs):3d} vtx  x[{lo[0]:5.0f},{hi[0]:5.0f}] y[{lo[1]:5.0f},{hi[1]:5.0f}] z[{lo[2]:5.0f},{hi[2]:5.0f}]'
        side = 'R' if x > 25 else 'L' if x < -25 else 'C'
        print(f'{b:3d}: parent {par:3d} obj {oi:3d} pos ({x:5.0f},{y:5.0f},{z:5.0f}) {side}  {part}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['video', 'sheet', 'bones', 'metrics'])
    ap.add_argument('out', nargs='?')
    ap.add_argument('models', nargs='+')
    ap.add_argument('--slot', type=lambda s: int(s, 0), default=2)
    ap.add_argument('--panels', default='mesh:side,skel:side,xray:front,gait')
    ap.add_argument('--cycles', type=int, default=3)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--size', type=int, default=360)
    ap.add_argument('--ticks', type=int, nargs='*')
    a = ap.parse_args()
    if a.cmd == 'metrics':
        a.models = ([a.out] if a.out else []) + a.models; return cmd_metrics(a)
    if a.cmd == 'bones':                       # bones MODEL: the out argument is the model
        a.models = ([a.out] if a.out else []) + a.models; return cmd_bones(a)
    models = [Model(s, a.slot) for s in a.models]
    rows = build(models, a.panels.split(','), a.size)
    n = max(len(m.frames) for m in models)
    if a.cmd == 'sheet':
        ticks = a.ticks or list(range(0, n, max(1, n // 8)))
        fr = [frame(rows, t, a.size // 2 if False else a.size) for t in ticks]
        W = max(f.width for f in fr)
        sheet = Image.new('RGB', (W, sum(f.height for f in fr)))
        y = 0
        for f in fr:
            sheet.paste(f, (0, y)); y += f.height
        sheet.save(a.out); print(a.out, sheet.size); return
    tmp = tempfile.mkdtemp(prefix='studio-', dir=os.environ.get('TMPDIR'))
    try:
        total = n * a.cycles
        for i in range(total):
            frame(rows, i, a.size).save(os.path.join(tmp, f'{i:05d}.png'))
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-framerate', str(20 * a.speed), '-i', os.path.join(tmp, '%05d.png'),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', a.out], check=True)
        print(a.out, total, 'frames')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
