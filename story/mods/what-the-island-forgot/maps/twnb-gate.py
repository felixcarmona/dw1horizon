#!/usr/bin/env python3
"""File City's lower town (TWNB01-24, screens 180-203, one per stage of the city's growth): the gate in the hedge that
leads to the Works (screen 357, the Stone Yard).

The gate is our own picture (art/twnb-gate.png, with transparency: a Nano Banana edit of a 4x enlargement of the
lower-left corner, design/prompts/twnb-gate/, cut out where all 24 backgrounds agree, so no stage's building is
touched). It is laid over each of the player's own 24 backgrounds at build time; nothing of the game's background is in
this folder. In every map: the steps and the mouth of the passage are step trigger 7 (the city's own exits are step
scripts 0-6): the story (arcs/works/gate.py) leads to the Stone Yard once Golemon has joined the city and turns the
tamer back before; the clipped hedge block beside them is a wall, the hedge's foreground pieces over the passage are
hidden (they would draw the old hedge over it), and exit 7 (a free slot) is the arrival from the Works, on the plaza.

    python3 twnb-gate.py OUT_DIR [NAME...]   writes OUT_DIR/TWNB01..24.MAP and .TFS (they replace the disc's; NAME...: only
                                             those, the same bytes: tools/derive makes them side by side)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, bg
from maps import reach

GATE_PNG = os.path.join(MOD, 'art', 'twnb-gate.png')
GATE_AT = (65, 505)                                     # top-left of the picture on the 768x640 background
WARP, STEP = 7, 7                                       # the arrival slot; the gate's step trigger (tile value 51 + STEP)
EXIT_PX = [(72, 630), (117, 630), (150, 585), (172, 552), (198, 552), (198, 518), (138, 518), (120, 543), (75, 605)]    # the steps and the passage's mouth
BLOCK_PX = [(152, 580), (175, 553), (212, 553), (214, 562), (198, 585), (178, 610), (150, 610)]    # the clipped hedge block
SPAWN_PX, ROTATION = (240, 505), 1024                   # on the plaza in front of the gate, facing east (+X)


def inside(poly, u, v):
    n, c = len(poly), False
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0): c = not c
    return c


def one(name, out, alpha):
    src = extracted(name)
    bg([src + '.MAP', src + '.TFS', os.path.join(out, name + '.TFS'),
        '--paste', GATE_PNG, str(GATE_AT[0]), str(GATE_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    # the hedge's foreground pieces that cover the passage (more than a sliver of it)
    X, Y = GATE_AT; H, W = len(alpha), len(alpha[0]); hidden = []
    for k in dwmap.covering_instances(m, X, Y, X + W, Y + H):
        inst = m.instances[k]; sp = m.sprites[inst['frames'][0]]
        x0, y0, x1, y1 = max(inst['x'], X), max(inst['y'], Y), min(inst['x'] + sp['width'], X + W), min(inst['y'] + sp['height'], Y + H)
        if sum(alpha[y][x] for y in range(y0 - Y, y1 - Y) for x in range(x0 - X, x1 - X)) >= 50: inst['flag'] = 1; hidden.append(k)
    col = list(m.collision); n = 0
    for tx, tz, u, v in cam.tiles():
        if u is None: continue
        if inside(BLOCK_PX, u, v): col[tz * 100 + tx] = 0x80
        elif inside(EXIT_PX, u, v): col[tz * 100 + tx] = 51 + STEP; n += 1
    m.collision = col
    sx, sz = cam.world(*SPAWN_PX); sx, sz = round(sx / 100) * 100 + 50, round(sz / 100) * 100 - 50
    m.warps[WARP].update({'x': sx, 'y': 0, 'z': sz, 'rotation': ROTATION})
    tx, tz = (sx + 5000) // 100, (5000 - sz) // 100
    if col[tz * 100 + tx] & 0x80: sys.exit(f'{name}: the arrival from the Works is not on a free tile')
    if any(col[(tz + dz) * 100 + tx + dx] == 51 + STEP for dx in (-1, 0, 1) for dz in (-1, 0, 1)): sys.exit(f'{name}: the arrival stands beside the gate')
    open(os.path.join(out, name + '.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(sx, sz)])
    if not any(((t % 100) * 100 - 4950 + dx, 4950 - (t // 100) * 100 + dz) in R
               for t, v in enumerate(col) if v == 51 + STEP for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit(f'{name}: the gate is not reachable from the plaza')
    return n, hidden, cam.pixel(sx, sz), (sx, sz)


def main(out, *only):
    os.makedirs(out, exist_ok=True)
    w, h, mode, rows, _ = dwmap.png_read(GATE_PNG, alpha=True)
    alpha = [[r[4 * x + 3] > 127 for x in range(w)] for r in rows]      # what bg --paste lays down
    for i in range(1, 25):
        if only and f'TWNB{i:02d}' not in only: continue
        n, hidden, sp, world = one(f'TWNB{i:02d}', out, alpha)
    print(f'TWNB01-24: the gate pasted, step {STEP} tiles {n}, hidden pieces {len(hidden)} (last), arrival px {sp} world {world}')


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(*sys.argv[1:])
