#!/usr/bin/env python3
"""adjust_arrivals.py TOUR.json ...: makes each segment's last waypoint the real exit to the next segment's screen: the warp of
the segment's map that targets that screen, pushed 300 units outward (the exit boxes sit at the edge beyond the arrival
point), projected to background pixels. The previous file is kept as TOUR.json.bak. Segments whose next screen has no
warp in the map (a scripted exit) are left alone."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import json, math, os, shutil, sys
sys.path.insert(0, os.path.join(_DEV_ROOT, 'tools'))
import dwmap
ROOT = _DEV_ROOT
for path in sys.argv[1:]:
    tour = json.load(open(path)); changed = 0
    for i, (scr, mapfile, route) in enumerate(tour[:-1]):
        nxt = tour[i + 1][0]
        m = dwmap.MapFile(open(os.path.join(ROOT, mapfile), 'rb').read())
        ws = [w for w in m.warps if w['targetMap'] == nxt]
        if not ws or not route: continue
        w = ws[0]
        free = [((tx - 50) * 100 + 50, (49 - tz) * 100 + 50) for tz in range(100) for tx in range(100) if m.collision[tz * 100 + tx] == 0]
        cx = sum(p[0] for p in free) / len(free); cz = sum(p[1] for p in free) / len(free)
        dx, dz = w['x'] - cx, w['z'] - cz; d = math.hypot(dx, dz) or 1.0
        bx, bz = w['x'] + dx / d * 300, w['z'] + dz / d * 300
        basis = dwmap.camera_basis(m)
        px = dwmap.project(m, basis, (bx, 0, bz))
        if not px: continue
        old = route[-1][0]
        route[-1][0] = [int(px[0]), int(px[1])]
        if old != route[-1][0]: changed += 1; print(f'{os.path.basename(path)}: screen {scr} -> {nxt}: exit waypoint {old} -> {route[-1][0]} (warp {w["x"]},{w["z"]})')
    if changed:
        shutil.copy(path, path + '.bak'); json.dump(tour, open(path, 'w')); print(f'{path}: {changed} exits fixed')
