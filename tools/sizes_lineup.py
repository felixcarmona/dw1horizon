#!/usr/bin/env python3
"""Lineup picture of species at the same scale (side view, idle pose), heights written.
  python3 tools/sizes_lineup.py OUT.png [--after] NAME ...      (names of the DW1 originals or imported species)
Imported species come from content/species (+ build/sizes-out/species with --after); the picture is made with
animsheet's rasterizer."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, glob, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd, animsheet, species, sizes

SC, S, SH = 0.55, 520, 640


def tris_of(m, bones):
    nb = len(bones)
    a = m.anims.anims[m.anims.table[0]]
    p = mmd.AnimPlayer(a, nb, 0); p.tick(stop_at_infinite_loop=True)
    pose = [list(v) for v in p.pose]; pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    W = [None] * nb
    def get(b):
        if W[b] is None:
            v = pose[b]; R = mmd.rot_matrix(*v[3:6])
            L = [[R[i][j] * v[j] / 4096 for j in range(3)] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            W[b] = mmd.mat_mul(get(bones[b][1]), L) if bones[b][1] >= 0 else L
        return W[b]
    tris = []
    for b, (oi, _) in enumerate(bones):
        if oi < 0: continue
        M = get(b)
        wv = [tuple(M[r][0] * x + M[r][1] * y + M[r][2] * z + M[r][3] for r in range(3)) for x, y, z, _ in m.tmd.obj_verts(oi)]
        for pr in m.tmd.objects[oi].prims:
            d = pr.decode(); ids = d['verts']
            for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else []):
                tris.append(([wv[ids[k]] for k in c], [d['uv'][k] for k in c] if d['uv'] else None, d))
    return tris


def load(name, after):
    O = species.originals()
    for t, r in enumerate(O.rec):
        if r['para']['name'].strip() == name and t < 180:
            if name == 'Megadramon' and t != 54: continue
            e = mmd.exe()
            m = mmd.MMD.load(O.model_path(t), t)
            return m, e.skeleton[t], mmd.load_tim(mmd.ALLTIM, t), r['para']['height'], r['para']['radius']
    dirs = [os.path.join(ROOT, 'build/sizes-out/species')] if after else []
    dirs.append(os.path.join(ROOT, 'content/species'))
    for d in dirs:
        for f in glob.glob(os.path.join(d, '*.json')):
            s = json.load(open(f))
            if s['name'] == name and 'para' in s:
                m = sizes.load_model(s['model']['file'], len(s['bones']))
                tim = mmd.Tim4(open(os.path.join(ROOT, s['texture']['file']), 'rb').read()[s['texture'].get('entry', 0) * 0x4800:][:0x4800])
                return m, s['bones'], tim, s['para']['height'], s['para']['radius']
    raise SystemExit(name + ': not found')


def main():
    out = sys.argv[1]; args = sys.argv[2:]
    after = '--after' in args; names = [a for a in args if a != '--after']
    n = len(names); Wd = S * n
    img = bytearray(bytes((40, 44, 52, 255)) * (Wd * SH))
    cam = animsheet.Camera(90, 0); labels = []
    for i, nm in enumerate(names):
        m, bones, tim, h, r = load(nm, after)
        tris = tris_of(m, bones)
        gy = SH - 70
        animsheet.raster(tris, cam, tim, SH, SC, S / 2, gy, img, i * S, Wd)
        # ground line and height label as a tick bar of the height
        pass
        labels.append((i * S + 8, SH - 55, f'{nm}  h {h}  r {r}'))
        print(nm, h, r)
    mmd.png_write(out, Wd, SH, bytes(img))
    from tools.image import Image, ImageDraw
    im = Image.open(out).convert('RGB'); d = ImageDraw.Draw(im)
    for x, y, t in labels:
        d.text((x, y), t, fill=(255, 255, 255))
    for h in (250, 500, 700, 900):
        y = SH - 70 - h * SC; d.line([(0, y), (Wd, y)], fill=(70, 76, 90)); d.text((4, y - 11), str(h), fill=(150, 160, 180))
    im.save(out)


main()
