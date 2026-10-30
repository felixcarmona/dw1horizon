#!/usr/bin/env python3
"""The Great Canyon Entrance with the stone bridge (screen 367, files GCAN21): screen 36 (GCAN01) after the Motor is
broken (R1, story-bible.md §3.2): the canyon has settled and the invisible bridge has turned to stone, seen and crossed
by anyone: an ancient, half-ruined bridge of worn blocks with one arch, and steps cut into the rock column at the far
end where the exit to 44 is (chosen from four concepts). The screen
runs screen 36's own script and setup ("like": 36), so its wild Digimon, chests and the bridge's step
scripts are the game's; the story sets the bridge's two flags with R1, so those scripts let the tamer across.
The three ways into 36 (TROP03's exit 0, DGHA01's exit 2, GCAN09's scripted way down) lead here once R1 is set
(maps/trop03-way.py, maps/dgha01-pass.py, arcs/canyon/stone-bridge.py).

The bridge is our own picture (art/gcan01-stone-bridge.png, with transparency: one Nano Banana edit of a 5x
enlargement of the gap, design/prompts/stone-bridge/, cut out where the answer differs from the player's background).
Its walkway is drawn over the invisible bridge's walkable strip (GCAN01 tiles x 46-53, z 0-34): the edit was given the
gap with that strip filled flat with the ledge's sand as a placeholder; given corner coordinates alone, the model
drew the bridge off the strip and the tamer walked on air.
It is laid over the player's own GCAN01 background at build time; nothing of the game's background is in this folder.

    python3 stone-bridge.py OUT_DIR        writes OUT_DIR/GCAN21.MAP and GCAN21.TFS (a new screen's files)
"""
import os, shutil, sys
from mapbase import extracted, dwmap, MOD, bg

BRIDGE_PNG = os.path.join(MOD, 'art', 'gcan01-stone-bridge.png')
BRIDGE_AT = (270, 10)                                   # top-left of the picture on the 640x768 background


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('GCAN01')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'GCAN21.TFS'),
        '--paste', BRIDGE_PNG, str(BRIDGE_AT[0]), str(BRIDGE_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read())
    from district_foreground import apply
    apply(m, 'stone-bridge', os.path.join(out, 'GCAN21.TFS'))
    open(os.path.join(out, 'GCAN21.MAP'), 'wb').write(m.build())
    print('GCAN21: the stone bridge pasted over GCAN01')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
