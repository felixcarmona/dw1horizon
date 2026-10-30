#!/usr/bin/env python3
"""The Drowned Shore (screen 309, files SHOR01): the old shoreline left under Freezeland's cliff when the island grew,
a beach of dark pebbles between the ice cliff and the black sea, with the wreck of the hundred-year-old human ship and
the soaked notebook among its planks (M12). Reached only by sea: Whamon's menu in the Secret Beach Cave (OGRE10) and
from Iceberg Beach (FRZL16); Whamon waits on the shore and the way out is by script, so the map has no exit tiles,
only the arrival point (warp 0, script use). Our art (art/drowned-shore.png, Nano Banana Pro with FRZL16's pitch: eye
6000 from the look-at point, 65 degrees down, projection 1100, 768x640) and our map data (drowned-shore-data.json,
made by author/drowned-shore-layout.py: the beach segmented from the art, the wreck blocked, the arrival); the
structure of the map (tile layout, TIMs, lights) is FRZL03's (a 768x640 Freezeland screen), read from the player's
own disc at build time, with the camera set here. Day, evening and night palettes are derived from the donor's.

    python3 drowned-shore.py OUT_DIR        writes OUT_DIR/SHOR01.MAP and SHOR01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'drowned-shore-data.json')
ART = os.path.join(MOD, 'art', 'drowned-shore.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('FRZL03', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SHOR01')
    import_png('FRZL03', ART, os.path.join(out, 'SHOR01.TFS'))
    apply_foreground(m, 'SHOR01', os.path.join(out, 'SHOR01.TFS'))
    open(os.path.join(out, 'SHOR01.MAP'), 'wb').write(m.build())
    print(f'SHOR01: free tiles {m.collision.count(0)}, arrival {(m.warps[0]["x"], m.warps[0]["z"])}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
