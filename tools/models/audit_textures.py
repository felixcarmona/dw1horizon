#!/usr/bin/env python3
"""Audit what every textured face of a model samples from its 4 bpp texture (the class of defect where a face shows
noise, an empty area or the wrong colours).

  tools/models/audit_textures.py disc DISC_DIR [ID ...] [--json OUT] [--all]
        every species of a built disc folder (DIGI.DAT, CHDAT/, ALLTIM.TIM): the model and texture the game loads
  tools/models/audit_textures.py originals [ID ...]      the 180 species of extracted/ (the reference: no error)
  tools/models/audit_textures.py file MODEL.MMD TEXTURE.TIM [ENTRY]

Each textured primitive is rasterised in texture space (the texel centres inside its UV triangles) and read through its
own CLUT row, the way the GPU reads it. Findings:

  row         the face's CLUT row is not in the texture (the GPU reads another model's palette)            error
  empty-row   the face's CLUT row is all 0x0000: the face is not drawn (an invisible placeholder, all
              texels colour 0 too, is reported as `invisible`: Cannondramon's attachment quads)             error
  outside     the face samples rows below the 256x128 image (VRAM that is not this texture)                  error
  invisible   at least 95 % of the face's texels are colour 0 (transparent) and the face is not semi-transparent
              (the disc hides faces this way on purpose: Mojyamon, Patamon, Piddomon)                       warning
  clut-area   the face samples the texture's own CLUT, stored inside the image by the source game
              (16 consecutive image words equal to a palette row): those texels are palette data, not art   error
  holes       at least 35 % (and 6) of the face's texels are transparent: a cut-out face, or a face that
              reaches past its island                                                                       warning
  noise       the face's texels change colour from one texel to the next far more than the model's other
              faces (median neighbour difference over the whole face)                                       warning

Thresholds are set so that no original species of the disc (`originals`) has an error; its warnings are the
baseline. Back faces are not considered: the game culls every primitive whose screen winding is clockwise (RotNclip),
the two sides of a thin plate are two primitives, and a renderer without culling shows them fighting (dots).
Standard library only.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import mmd  # noqa: E402

INVISIBLE = 0.95
HOLES, HOLES_MIN = 0.35, 6
NOISE = 0.30            # median neighbour difference (0..1 of the RGB diagonal) for a noise warning
NOISE_MIN_PAIRS = 12
CLUT_BASE = 488         # CBA row of the model's first CLUT row (model.c)


def row_of(cba):
    return (cba >> 6) - CLUT_BASE


def texels(uv, w=256, h=256):
    """The texel (x, y) whose centres lie in the UV polygon (3 or 4 points in TMD order; a quad is the triangles 0 1 2
    and 1 3 2). A degenerate triangle gives its corner texels."""
    tris = [(uv[0], uv[1], uv[2])] + ([(uv[1], uv[3], uv[2])] if len(uv) == 4 else [])
    out = set()
    for a, b, c in tris:
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if area == 0:
            out |= {(min(p[0], w - 1), min(p[1], h - 1)) for p in (a, b, c)}
            continue
        s = 1 if area > 0 else -1
        x0, x1 = max(0, min(a[0], b[0], c[0])), min(w - 1, max(a[0], b[0], c[0]))
        y0, y1 = max(0, min(a[1], b[1], c[1])), min(h - 1, max(a[1], b[1], c[1]))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px, py = x + .5, y + .5
                if all(s * ((q[0] - p[0]) * (py - p[1]) - (q[1] - p[1]) * (px - p[0])) >= 0
                       for p, q in ((a, b), (b, c), (c, a))):
                    out.add((x, y))
    if not out:
        out = {(min(p[0], w - 1), min(p[1], h - 1)) for p in uv}
    return out


def clut_area(tim):
    """Texels of the image that hold a copy of one of the texture's palette rows (16 words = 64 texels of one row)."""
    words = []
    for y in range(tim.h):
        row = tim.idx[y * tim.w:(y + 1) * tim.w]
        words.append([row[i] | row[i + 1] << 4 | row[i + 2] << 8 | row[i + 3] << 12 for i in range(0, tim.w, 4)])
    pals = [tuple(p) for p in tim.pal if sum(1 for c in p if c) >= 4]
    area = set()
    for y, ws in enumerate(words):
        for x in range(len(ws) - 15):
            if tuple(ws[x:x + 16]) in pals:
                area |= {(x * 4 + k, y) for k in range(64)}
    return area


def colour(c):
    return ((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3)


def audit(tmd, tim):
    """One dict per textured primitive: obj, prim, row, uv, find [(kind, text)], and the measures n (texels), clear
    (fraction transparent) and noise (median neighbour difference) when they apply."""
    W, H = tim.w, tim.h
    carea = clut_area(tim)
    faces = []
    for oi, ob in enumerate(tmd.objects):
        for pi, p in enumerate(ob.prims):
            if not p.mode & 4 or p.mode >> 5 != 1:
                continue
            d = p.decode()
            row = row_of(d['cba'])
            f = dict(obj=oi, prim=pi, row=row, uv=d['uv'], semi=bool(p.mode & 2), find=[])
            faces.append(f)
            if not 0 <= row < tim.ch:
                f['find'].append(('row', f'CLUT row {row} (texture has {tim.ch})'))
                continue
            pal = tim.pal[row]
            inside = [(x, y) for x, y in texels(d['uv'], W, 256) if y < H]
            f['n'] = len(inside)
            if not any(pal):
                if inside and not any(tim.idx[y * W + x] for x, y in inside):
                    f['find'].append(('invisible', f'CLUT row {row} is all 0x0000 and the texels are all colour 0'))
                else:
                    f['find'].append(('empty-row', f'CLUT row {row} is all 0x0000'))
                continue
            if any(v >= H for _, v in d['uv']):
                f['find'].append(('outside', f'V up to {max(v for _, v in d["uv"])} (image rows 0..{H - 1})'))
            if not inside:
                continue
            cols = {(x, y): pal[tim.idx[y * W + x]] for x, y in inside}
            clear = sum(1 for c in cols.values() if c == 0)
            f['clear'] = clear / len(inside)
            if not f['semi'] and f['clear'] >= INVISIBLE:
                f['find'].append(('invisible', f'{clear}/{len(inside)} texels transparent'))
            elif clear >= HOLES_MIN and f['clear'] >= HOLES:
                f['find'].append(('holes', f'{clear}/{len(inside)} texels transparent'))
            ca = sum(1 for t in inside if t in carea)
            if ca:
                f['find'].append(('clut-area', f'{ca}/{len(inside)} texels are the texture\'s palette data'))
            diffs = []
            for (x, y), c in cols.items():
                for n in ((x + 1, y), (x, y + 1)):
                    if n in cols and c and cols[n]:
                        a, b = colour(c), colour(cols[n])
                        diffs.append(sum((a[i] - b[i]) ** 2 for i in range(3)) ** .5 / 441.7)
            if len(diffs) >= NOISE_MIN_PAIRS:
                diffs.sort()
                f['noise'] = diffs[len(diffs) // 2]
                if f['noise'] >= NOISE:
                    f['find'].append(('noise', f'median neighbour difference {f["noise"]:.2f}'))
    return faces


ERRORS = {'row', 'empty-row', 'outside', 'clut-area'}


def summary(faces):
    out = {}
    for f in faces:
        for kind, _ in f['find']:
            out[kind] = out.get(kind, 0) + 1
    return out


def load_pair(model_bytes, tim_bytes):
    return mmd.TMD.parse(model_bytes, struct.unpack_from('<I', model_bytes, 0)[0]), mmd.Tim4(tim_bytes)


def disc_models(disc, ids=None):
    """(id, name, model bytes, texture bytes) of every species a built disc folder carries."""
    import species
    disc = Path(disc)
    d, count, recs = species.read_archive(str(disc / 'DIGI.DAT'))
    alltim = (disc / 'CHDAT' / 'ALLTIM.TIM').read_bytes()
    files = {p.stem.upper(): p for p in (disc / 'CHDAT').glob('MMD*/*.MMD')}
    for r in recs:
        t = r['id']
        if ids and t not in ids:
            continue
        name = r['para'].get('name') if isinstance(r.get('para'), dict) else None
        if r['modelSize']:
            model = d[r['modelSector'] * species.SECTOR:r['modelSector'] * species.SECTOR + r['modelSize']]
        elif r['modelName'] and r['modelName'].upper() in files:
            model = files[r['modelName'].upper()].read_bytes()
        else:
            continue
        src = d if r['texFile'] == species.TEX_ARCHIVE else alltim
        tim = src[r['texSector'] * species.SECTOR:(r['texSector'] + r['texSectors']) * species.SECTOR]
        if len(tim) < 20 or struct.unpack_from('<I', tim, 0)[0] != 0x10:
            continue
        yield t, name or r['modelName'] or str(t), model, tim


def original_models(ids=None):
    import species
    e = mmd.exe()
    alltim = os.path.join(mmd.EXTRACTED, 'CHDAT', 'ALLTIM.TIM')
    data = Path(alltim).read_bytes()
    for t in range(180):
        if ids and t not in ids:
            continue
        path = species.originals().model_path(t)
        if not path or not os.path.exists(path):
            continue
        yield t, e.name(t), Path(path).read_bytes(), mmd.alltim_entry(data, t)


def run(models, show_all=False):
    report = {}
    for t, name, model, tim in models:
        try:
            tmd, tm = load_pair(model, tim)
        except Exception as ex:             # noqa: BLE001 - a broken file is itself a finding
            report[t] = dict(name=name, error=repr(ex))
            continue
        faces = audit(tmd, tm)
        found = [dict(obj=f['obj'], prim=f['prim'], row=f['row'], uv=f['uv'], find=f['find']) for f in faces if f['find']]
        s = summary(faces)
        if found or show_all:
            report[t] = dict(name=name, faces=len(faces), summary=s, errors=sum(v for k, v in s.items() if k in ERRORS),
                             found=found)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('disc'); a.add_argument('disc'); a.add_argument('ids', nargs='*', type=int)
    a = sub.add_parser('originals'); a.add_argument('ids', nargs='*', type=int)
    a = sub.add_parser('file'); a.add_argument('model'); a.add_argument('tim'); a.add_argument('entry', nargs='?', type=int)
    for p in sub.choices.values():
        p.add_argument('--json'); p.add_argument('--all', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'disc':
        models = disc_models(a.disc, set(a.ids))
    elif a.cmd == 'originals':
        models = original_models(set(a.ids))
    else:
        tim = Path(a.tim).read_bytes()
        if a.entry is not None:
            tim = mmd.alltim_entry(tim, a.entry)
        models = [(0, os.path.basename(a.model), Path(a.model).read_bytes(), tim)]
    report = run(models, a.all)
    bad = 0
    for t, r in sorted(report.items()):
        if 'error' in r:
            print(f'{t:4d} {r["name"]}: unreadable: {r["error"]}'); bad += 1; continue
        if not r['summary']:
            continue
        print(f'{t:4d} {r["name"]}: {r["faces"]} faces; ' + ', '.join(f'{k} {v}' for k, v in sorted(r['summary'].items())))
        bad += bool(r['errors'])
    if a.json:
        Path(a.json).write_text(json.dumps({str(k): v for k, v in sorted(report.items())}, indent=1) + '\n')
    print(f'{len(report)} models with findings, {bad} with errors')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
