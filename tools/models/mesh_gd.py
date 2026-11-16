"""Reviewed crown/card diagonals and bounded panel fits for 307/314/323/326.

The opposite sides of a thin sheet must use the same GPU diagonal. Rotating
its back packet's corner order preserves winding, boundary and corner data.
The panel fits move shared vertices together, within four local units and the
original bone bounds. They retain the artist's normals and every animation.
"""
import json
from pathlib import Path

import mmd

FITS = Path(__file__).resolve().parents[2] / 'content/models/authoring/mesh-gd-fits.json'
IDS = (307, 314, 323, 326)


def apply(model, sid):
    rows = json.loads(FITS.read_text())
    sid = str(sid)
    diagonals = rows['diagonals'].get(sid, [])
    fits = rows['fits'].get(sid, [])
    for oi, pi, vertices in diagonals:
        obj = model.tmd.objects[oi]
        d = obj.prims[pi].decode()
        if d['verts'] != vertices:
            raise ValueError(f'{sid}: reviewed sheet corners changed')
        for attr in ('verts', 'uv', 'norms', 'colors'):
            if len(d[attr]) == 4:
                d[attr] = [d[attr][k] for k in (1, 3, 0, 2)]
        obj.prims[pi] = mmd.Prim.encode(d)
    for oi, vi, before, after in fits:
        obj = model.tmd.objects[oi]
        old = model.tmd.verts[obj.vert_start+vi]
        if list(old[:3]) != before:
            raise ValueError(f'{sid}: reviewed panel vertex changed')
        if sum((a-b)**2 for a, b in zip(after, before)) > 16:
            raise ValueError(f'{sid}: panel exceeds four-unit fit')
        model.tmd.verts[obj.vert_start+vi] = tuple(after)+(old[3],)
    return dict(aligned_back_diagonals=len(diagonals), fitted_vertices=len(fits))
