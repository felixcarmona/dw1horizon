#!/usr/bin/env python3
"""The Passage (screen 305, files PASS01): MasterTyrannomon's secret trail out of the Ancient Glacial Region, a narrow
winding path of golden dirt through the ancient jungle where time almost stands still (droplets and leaves hang in
the air), turning to grey rock at the far end where the fast-time wasteland begins. Our art (art/passage.png, Nano
Banana Pro with KODA03's camera: eye 4946 from the look-at point, 43 degrees down, projection 618, a 640x768
portrait) and our map data (passage-data.json, made by author/passage-layout.py: the trail segmented from the art,
the exits, the Glacial Region's lights); the structure of the map (tile layout, TIMs) is KODA08's (a 640x768 Speedy
Region screen; no 512x768 screen exists on the disc), read from the player's own disc at build time, with the camera
set here. Day, evening and night palettes are derived from the donor's.

    python3 passage.py OUT_DIR        writes OUT_DIR/PASS01.MAP and PASS01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'passage-data.json')
ART = os.path.join(MOD, 'art', 'passage.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('KODA08', *d['camera']); m.projection = d['projection']; m.lights = d['lights']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'PASS01')
    import_png('KODA08', ART, os.path.join(out, 'PASS01.TFS'))
    apply_foreground(m, 'PASS01', os.path.join(out, 'PASS01.TFS'))
    open(os.path.join(out, 'PASS01.MAP'), 'wb').write(m.build())
    print(f'PASS01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
