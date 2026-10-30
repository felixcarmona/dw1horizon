#!/usr/bin/env python3
"""The Bone Field (screen 306, files BONE01): the battlefield of the old war at the end of MasterTyrannomon's secret
trail, in the grey fast-time wasteland: giant half-buried bones, impact craters, machine wreckage grown into the rock,
a fallen human banner and an unnamed grave; MasterTyrannomon and Brachiomon tell how it ended (M11). Our art
(art/bone-field.png, Nano Banana Pro with KODA07's pitch and pixel scale: eye 6000 from the look-at point, 48 degrees
down, projection 820, a 768x640 landscape) and our map data (bone-field-data.json, made by author/bone-field-layout.py:
the open ground segmented from the art, the exits); the structure of the map (tile layout, TIMs, lights) is KODA04's
(a 768x640 Speedy Region screen), read from the player's own disc at build time, with the camera set here. Day,
evening and night palettes are derived from the donor's.

    python3 bone-field.py OUT_DIR        writes OUT_DIR/BONE01.MAP and BONE01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'bone-field-data.json')
ART = os.path.join(MOD, 'art', 'bone-field.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('KODA04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'BONE01')
    import_png('KODA04', ART, os.path.join(out, 'BONE01.TFS'))
    apply_foreground(m, 'BONE01', os.path.join(out, 'BONE01.TFS'))
    open(os.path.join(out, 'BONE01.MAP'), 'wb').write(m.build())
    print(f'BONE01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
