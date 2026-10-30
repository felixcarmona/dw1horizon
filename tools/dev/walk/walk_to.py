#!/usr/bin/env python3
"""Walk the tamer to a world point with the pad, on the running emulator (EMU_PORT, DW_SYMS).

  walk_to.py MAPFILE X Z UPX UPZ RIGHTX RIGHTZ
MAPFILE: the screen's .MAP (extracted/MAP/...); X Z: the target; UP*/RIGHT*: the world direction the pad's UP and RIGHT
move the tamer on this screen (measure them: press each and read tamer.location), DOWN and LEFT the opposite. E.g.
Gear Savanna 131: 1 1 1 -1. It plans over the engine's reachable lattice (reach.py), from the target, and holds the
one or two buttons closest to a point 250 units ahead on that path, again and again, until within 40 units.

Unlike `game_state.py move`, the camera follows (a teleport leaves it behind on scrolling screens: the tamer off
screen, sometimes stuck in a blocked tile). Prints `arrived X Z`, `stuck X Z` or `gave up`.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, os, math, time, subprocess, collections
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap; from tools.dev import emulator as emu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maps import reach


def location():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py'), 'show', 'tamer.location'],
                         capture_output=True, text=True).stdout
    v = [int(a) for a in out.split('[')[1].split(']')[0].split(',')]
    return v[0], v[2]


def main():
    if len(sys.argv) != 8: sys.exit(__doc__)
    m = dwmap.MapFile(open(sys.argv[1], 'rb').read())
    tx, tz = int(sys.argv[2]), int(sys.argv[3])
    up, right = (float(sys.argv[4]), float(sys.argv[5])), (float(sys.argv[6]), float(sys.argv[7]))
    combos = []
    for u in (-1, 0, 1):
        for r in (-1, 0, 1):
            if u or r:
                v = (u * up[0] + r * right[0], u * up[1] + r * right[1]); n = math.hypot(*v)
                combos.append(((v[0] / n, v[1] / n), ([('UP' if u > 0 else 'DOWN')] if u else []) +
                               ([('RIGHT' if r > 0 else 'LEFT')] if r else [])))
    free = reach.from_spawn_coordinates(m)
    goal = min(free, key=lambda p: (p[0] - tx) ** 2 + (p[1] - tz) ** 2)
    nxt = {goal: None}; q = collections.deque([goal])        # every reachable point knows its next step to the goal
    while q:
        c = q.popleft()
        for d in ((10, 0), (-10, 0), (0, 10), (0, -10)):
            n = (c[0] + d[0], c[1] + d[1])
            if n in free and n not in nxt: nxt[n] = c; q.append(n)
    last, stuck = None, 0
    for _ in range(400):
        x, z = location()
        if math.hypot(x - tx, z - tz) < 40: print('arrived', x, z); return
        a = min(nxt, key=lambda p: (p[0] - x) ** 2 + (p[1] - z) ** 2)
        for _ in range(25):
            if nxt[a] is None: break
            a = nxt[a]
        v = (a[0] - x, a[1] - z); n = math.hypot(*v) or 1
        buttons = max(combos, key=lambda c: (c[0][0] * v[0] + c[0][1] * v[1]) / n)[1]
        for b in buttons: emu.api(f'/api/v1/lua/press?button={b}')
        try: time.sleep(0.12 if n < 120 else 0.25)
        finally:
            for b in buttons: emu.api(f'/api/v1/lua/release?button={b}')
        stuck = stuck + 1 if last == (x, z) else 0; last = (x, z)
        if stuck > 8: print('stuck', x, z); return
    print('gave up', location())


if __name__ == '__main__':
    main()
