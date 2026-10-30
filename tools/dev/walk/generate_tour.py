#!/usr/bin/env python3
"""generate_tour.py MAPS_DIR OUT.json SCREEN:EXIT[,SCREEN:EXIT...]  [--names FILE=SCREEN...]
A tour (tools/dev/walk/tour.py) through a path of screens: on each screen the tamer walks to the floor's centre, then to the
exit named (the warp's arrival point pushed 300 units outward, as adjust_arrivals.py does), which takes it to the next screen;
EXIT '-' means "stay: walk the centre and every exit's arrival (pulled 300 units inward) without leaving" (the last screen
of a path, or a single screen). MAPS_DIR holds the built maps (build/what-the-island-forgot-maps/screens); the screen's file comes from the mod's screen files
(story/mods/what-the-island-forgot/screens/<id>-*.json).
    tools/dev/walk/generate_tour.py build/what-the-island-forgot-maps/screens build/new-maps/tours/tour-loop1.json 337:1,338:1,339:1,340:1,343:0,342:0,341:0,337:-
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import glob, json, math, os, sys
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap
maps_dir, out, path = sys.argv[1:4]
def screen_file(scr):
    f = glob.glob(os.path.join(ROOT, 'story/mods/what-the-island-forgot/screens', f'{scr}-*.json'))
    if not f: sys.exit(f'no screen file for {scr}')
    return json.load(open(f[0]))['file']
tour = []
for step in path.split(','):
    scr, ex = step.split(':'); scr = int(scr)
    mp = os.path.join(maps_dir, screen_file(scr) + '.MAP'); m = dwmap.MapFile(open(mp, 'rb').read()); basis = dwmap.camera_basis(m)
    free = [((tx - 50) * 100 + 50, (49 - tz) * 100 + 50) for tz in range(100) for tx in range(100) if m.collision[tz * 100 + tx] == 0]
    cx = sum(p[0] for p in free) / len(free); cz = sum(p[1] for p in free) / len(free)
    c = dwmap.project(m, basis, (cx, 0, cz)); centre = [int(c[0]), int(c[1])]
    def beyond(w):
        dx, dz = w['x'] - cx, w['z'] - cz; d = math.hypot(dx, dz) or 1.0
        p = dwmap.project(m, basis, (w['x'] + dx / d * 300, 0, w['z'] + dz / d * 300)); return [int(p[0]), int(p[1])] if p else None
    route = [[centre, 1]]
    if ex == '-':
        for w in m.warps:                      # each arrival pulled 300 units inward: walked to the arrival itself, the tamer's
            if w['targetMap'] == -1: continue  # overshoot (a pad hold is up to ~300 units) carried it into the exit box
            dx, dz = cx - w['x'], cz - w['z']; d = math.hypot(dx, dz) or 1.0
            p = dwmap.project(m, basis, (w['x'] + dx / d * 300, 0, w['z'] + dz / d * 300))
            if p: route += [[[int(p[0]), int(p[1])], 1], [centre, 0]]
    else:
        w = m.warps[int(ex)]
        if w['targetMap'] == -1: sys.exit(f'screen {scr}: exit {ex} has no target')
        b = beyond(w); route.append([b, 0])
    tour.append([scr, os.path.relpath(mp, ROOT), route])
    print(scr, screen_file(scr), 'centre', centre, 'route', [p for p, _ in route])
json.dump(tour, open(out, 'w')); print('wrote', out)
