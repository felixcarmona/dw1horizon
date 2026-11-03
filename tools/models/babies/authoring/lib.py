"""Authoring kit of the hand-made babies (developer only: NumPy and OpenCV, the repository's .venv).

A DW1 donor's MMD + texture page from extracted/, edited by one script per baby, rendered with tools/animstudio.py.
Each script writes build/babies-authoring/<Name>.MMD/.TIM (BABIES_OUT overrides); store an approved pair with
`python3 -m tools.models.babies encode ID MMD TIM` (the build replays those deltas, never these scripts):

  .venv/bin/python tools/models/babies/authoring/pabumon.py         # every baby, then:
  .venv/bin/python tools/models/babies/authoring/shrink.py build/babies-authoring
  python3 -m tools.models.babies encode 470 build/babies-authoring/Pabumon.MMD build/babies-authoring/Pabumon.TIM
"""
import os, sys, subprocess, struct, math
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../../..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import mmd  # noqa
OUT = os.environ.get('BABIES_OUT') or os.path.join(REPO, 'build/babies-authoring')
CH = os.path.join(REPO, 'extracted/CHDAT')
DONORS = {1: 'MMD0/BOTA', 15: 'MMD0/PUNI', 29: 'MMD0/POYO', 43: 'MMD1/YURA', 2: 'MMD0/KORO',
          16: 'MMD0/TUNO', 30: 'MMD1/TOKO', 44: 'MMD1/TANE'}


class Baby:
    def __init__(self, name, donor):
        self.name, self.type = name, donor
        self.path = os.path.join(CH, DONORS[donor] + '.MMD')
        self.m = mmd.MMD.load(self.path, donor)
        self.tim = mmd.load_tim(os.path.join(CH, 'ALLTIM.TIM'), donor)
        self.pm = np.array(mmd.palette_map(self.m, self.tim)).reshape(self.tim.h, self.tim.w)
        self.tex = np.frombuffer(bytes(mmd.texture_rgba(self.m, self.tim)), np.uint8).reshape(self.tim.h, self.tim.w, 4).copy()
        self.used = self._used_mask()

    def _used_mask(self):
        """Pixels some primitive samples (UV triangles) or a texture animation copies from."""
        H, W = self.tim.h, self.tim.w
        mask = np.zeros((H, W), np.uint8)
        for ob in self.m.tmd.objects:
            for p in ob.prims:
                d = p.decode()
                if not d['uv']: continue
                uv = d['uv']
                for tri in ([0, 1, 2], [1, 3, 2]) if len(uv) == 4 else ([0, 1, 2],):
                    cv2.fillPoly(mask, [np.array([uv[k] for k in tri], np.int32)], 1)
        for a in self.m.anims.anims:
            for ins in a.instrs:
                if ins['op'] == 'tex':
                    (sx, sy), (w, h), _ = ins['src'], ins['size'], ins['dst']
                    mask[sy:sy + h, sx * 4:sx * 4 + w * 4] = 1
        return mask.astype(bool)

    # ---- geometry
    def objects(self):
        return range(len(self.m.tmd.objects))

    def warp(self, oi, f):
        """f(x, y, z) -> (x, y, z) on every vertex of object oi (bone-local; y negative = up)."""
        ob = self.m.tmd.objects[oi]
        for i in range(ob.vert_start, ob.vert_start + ob.nvert):
            x, y, z, p = self.m.tmd.verts[i]
            nx, ny, nz = f(x, y, z)
            self.m.tmd.verts[i] = (int(round(max(-32768, min(32767, nx)))), int(round(max(-32768, min(32767, ny)))),
                                   int(round(max(-32768, min(32767, nz)))), p)

    def verts(self, oi):
        return np.array([v[:3] for v in self.m.tmd.obj_verts(oi)], float)

    def hide(self, oi):
        """Collapse an object to a point (no geometry drawn)."""
        vs = self.verts(oi); c = vs.mean(0)
        self.warp(oi, lambda x, y, z: (c[0], c[1], c[2]))

    def tex_anims(self):
        out = set()
        for a in self.m.anims.anims:
            for ins in a.instrs:
                if ins['op'] == 'tex':
                    (sx, sy), (w, h), (dx, dy) = ins['src'], ins['size'], ins['dst']
                    out.add(((sx * 4, sy, w * 4, h), (dx * 4, dy)))
        return sorted(out)

    # ---- save / render
    def save(self):
        tex = self.tex.copy()
        mmd.tex_import(self.m, self.tim, self.tim.w, self.tim.h, bytearray(tex.tobytes()))
        os.makedirs(OUT, exist_ok=True)
        mp, tp = os.path.join(OUT, self.name + '.MMD'), os.path.join(OUT, self.name + '.TIM')
        open(mp, 'wb').write(self.m.build())
        open(tp, 'wb').write(self.tim.to_bytes())
        cv2.imwrite(os.path.join(OUT, self.name + '-tex.png'),
                    cv2.resize(cv2.cvtColor(self.tex, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
        return f'{mp}:{self.type}:{tp}:0:{self.name}'


def sheet(out, specs, panels='mesh:front,mesh:three,mesh:side,mesh:back', size=220, ticks=(0,)):
    if os.environ.get('BABIES_NOSHEET'):           # (a batch rebuild: models only)
        return out
    cmd = [os.path.join(REPO, '.venv/bin/python'), os.path.join(REPO, 'tools/animstudio.py'), 'sheet', out] + list(specs) + \
          ['--slot', '0', '--panels', panels, '--size', str(size), '--ticks'] + [str(t) for t in ticks]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-2000:])
    return out


# ---- colour helpers (numpy RGBA pages)
def hsv(tex):
    return cv2.cvtColor(np.ascontiguousarray(tex[..., :3]), cv2.COLOR_RGB2HSV_FULL).astype(float)


def lum(tex):
    return tex[..., :3].astype(float) @ [0.299, 0.587, 0.114] / 255.0


def ramp(t, stops):
    """t in 0..1 (array) -> RGB along colour stops [(t0,(r,g,b)), ...]."""
    t = np.clip(t, 0, 1)
    xs = [s[0] for s in stops]
    return np.stack([np.interp(t, xs, [s[1][k] for s in stops]) for k in range(3)], -1)


def put(tex, mask, rgb):
    tex[..., :3] = np.where(mask[..., None], np.clip(rgb, 0, 255), tex[..., :3]).astype(np.uint8)
