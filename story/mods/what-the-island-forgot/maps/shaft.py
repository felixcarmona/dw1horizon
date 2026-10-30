#!/usr/bin/env python3
"""The Shaft (screen 302, files SHFT01): the bottom of the Ogre Fortress elevator. The art is MGEN17, the Back-Dimension
variant the game never uses, read from the player's own disc; the collision and camera are MGEN17's. Ours are the exits:
the red circle at the top right is the elevator's landing (exit 0 <-> OGRE03, the elevator room, exit 1) and the green
wireframe vortex in the bottom-left corner (a walkable cell joined to the left block, unused by the game) leads to the
Engine Room (exit 1 <-> screen 300 exit 0). The files get a name of their own so
they do not clash with the Silent Horn DLC, which uses MGEN17's.

    python3 shaft.py OUT_DIR        writes OUT_DIR/SHFT01.MAP and SHFT01.TFS
"""
import math, os, shutil, sys
from mapbase import extracted, Cam, reachable, dwmap, inside

ELEVATOR = [(500 + 38 * math.cos(a * math.pi / 8), 100 + 27 * math.sin(a * math.pi / 8)) for a in range(16)]   # the whole red circle
VORTEX = [(215 + 42 * math.cos(a * math.pi / 8), 512 + 30 * math.sin(a * math.pi / 8)) for a in range(16)]   # the vortex's mouth
SPAWN_ELEVATOR, FACE_ELEVATOR = (445, 140), (380, 175)      # arriving from the Fortress: beside the circle, clear of it
SPAWN_VORTEX, FACE_VORTEX = (180, 415), (120, 330)          # arriving from the Engine Room: beside the vortex, on the left block


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('MGEN17')
    shutil.copy(src + '.TFS', os.path.join(out, 'SHFT01.TFS'))
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz, u, v in cam.tiles():
        if col[tz * 100 + tx] & 0x80 or u is None: continue
        if inside(ELEVATOR, u, v): col[tz * 100 + tx] = 110
        elif inside(VORTEX, u, v): col[tz * 100 + tx] = 111
    m.collision = col
    for w in m.warps: w.update({'targetMap': -1, 'targetExit': -1})
    a = cam.world(*SPAWN_ELEVATOR); m.warps[0].update({'x': a[0], 'z': a[1], 'rotation': cam.rotation(a, cam.world(*FACE_ELEVATOR)), 'targetMap': 48, 'targetExit': 1})
    b = cam.world(*SPAWN_VORTEX); m.warps[1].update({'x': b[0], 'z': b[1], 'rotation': cam.rotation(b, cam.world(*FACE_VORTEX)), 'targetMap': 300, 'targetExit': 0})
    m.warps[2].update({'x': 0, 'z': 0, 'rotation': 0})
    open(os.path.join(out, 'SHFT01.MAP'), 'wb').write(m.build())
    R = reachable(m)
    for name, p in (('elevator', a), ('vortex', b)):
        if (round(p[0] / 10) * 10, round(p[1] / 10) * 10) not in R: sys.exit(f'the {name} spawn is not reachable')
    print(f'SHFT01: free tiles {col.count(0)}, elevator tiles {col.count(110)}, vortex tiles {col.count(111)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
