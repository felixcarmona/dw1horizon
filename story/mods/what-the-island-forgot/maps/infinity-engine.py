#!/usr/bin/env python3
"""The Infinity Engine room (screen 312, files INFE01; and its dark state, screen 313, files INFE02): Analogman's
program, the hall of circuit blocks high inside Mt. Infinity between Megadramon's screen (MGEN10, 254) and
MetalGreymon's (MGEN98, 222): consoles and cables, the third notebook on a console, and at the back the empty door
frame made of circuitry, lit from within. With R1+R2+R3 broken the lights are dead and the circuitry shows red error
patterns (screen 313, same floor, our second picture). Our art (art/infinity-engine.png, art/infinity-engine-dark.png,
Nano Banana Pro with MGEN10's camera: eye 11270 from the look-at point, 51 degrees down, projection 927, 768x640) and
our map data (infinity-engine-data.json, made by author/infinity-engine-layout.py: the floor segmented from the art,
the consoles blocked, the exits); the structure of the map (tile layout, lights; no TIMs) is MGEN10's, read from the
player's own disc at build time, with the camera set here. Exit 0 (south band) → 254, exit 1 (the passage at the back
left) → 222 exit 0; the scripts of 254 and 247 (Devimon's shortcut) that today jump straight to 222 are story work.

    python3 infinity-engine.py OUT_DIR        writes OUT_DIR/INFE01.MAP, INFE01.TFS and, if the dark picture exists, INFE02.MAP, INFE02.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'infinity-engine-data.json')
ARTS = [('INFE01', os.path.join(MOD, 'art', 'infinity-engine.png')), ('INFE02', os.path.join(MOD, 'art', 'infinity-engine-dark.png'))]


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    for name, art in ARTS:
        if not os.path.exists(art): continue
        m = base_map('MGEN10', *d['camera']); m.projection = d['projection']
        m.collision = list(d['collision']); m.warps = d['warps']
        check_arrivals(m, name)
        import_png('MGEN10', art, os.path.join(out, name + '.TFS'))
        apply_foreground(m, name, os.path.join(out, name + '.TFS'))
        open(os.path.join(out, name + '.MAP'), 'wb').write(m.build())
        print(f'{name}: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
