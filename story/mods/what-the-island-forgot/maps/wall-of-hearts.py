#!/usr/bin/env python3
"""The Wall of Hearts (screen 310, files VALT01; and its melted state, screen 311, files VALT02): the Vault beneath the
Ice Sanctuary's hidden hall, the chamber of the decision R3: a vast wall of ice standing on the far edge of a glass
circuit floor, with the frozen memories (the old town's buildings, landmarks, the faces of many Digimon) trapped inside;
after "Stay" the wall is melted into a curtain of water (screen 311, same floor, our second picture). The story takes the
tamer down from Angemon's pedestal (screen 97, arcs/vault/statue-room.py: the hidden hall 104 holds the post-game's
Machinedramon and Analogman at every hour, so it is no way in mid-game); the bottom band (exit 0) climbs back to the
statue room's door (97, entry 0, the only arrival it has). The gateway pasted into 104's north edge (icsa08-north.py)
still leads here; dead end. Our art (art/wall-of-hearts.png and
art/wall-of-hearts-melted.png, Nano Banana Pro with ICSA08's camera: eye 7224 from the look-at point, 62 degrees down,
projection 927, 768x640) and our map data (wall-of-hearts-data.json, made by author/wall-of-hearts-layout.py: the
floor segmented from the art, the exit); the structure of the map (tile layout, the one 4-bpp TIM, lights) is ICSA08's,
read from the player's own disc at build time, with the camera set here.

    python3 wall-of-hearts.py OUT_DIR        writes OUT_DIR/VALT01.MAP, VALT01.TFS and, if the melted picture exists, VALT02.MAP, VALT02.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'wall-of-hearts-data.json')
BACK = (97, 0)                                          # exit 0 climbs back to the statue room
ARTS = [('VALT01', os.path.join(MOD, 'art', 'wall-of-hearts.png')), ('VALT02', os.path.join(MOD, 'art', 'wall-of-hearts-melted.png'))]


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    for name, art in ARTS:
        if not os.path.exists(art): continue
        m = base_map('ICSA08', *d['camera']); m.projection = d['projection']
        m.collision = list(d['collision']); m.warps = d['warps']
        m.warps[0].update({'targetMap': BACK[0], 'targetExit': BACK[1]})
        check_arrivals(m, name)
        open(os.path.join(out, name + '.MAP'), 'wb').write(m.build())
        import_png('ICSA08', art, os.path.join(out, name + '.TFS'))
        print(f'{name}: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
