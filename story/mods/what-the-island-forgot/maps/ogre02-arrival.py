#!/usr/bin/env python3
"""Ogre Fortress (OGRE02, screen 47): the arrival from the elevator side (OGRE03 exit 0, this map's exit 1) clear of Machinedramon.

The original spawns that arrival at (-363, 942), 150 units in front of the post-game Machinedramon at (-156, 1092). Its body box
(radius 250) plus the tamer's 100 covers it, and a tamer that starts inside a body box cannot move again. The arrival moves to the
open floor west of the box, still just inside the north door; heading, target and every other exit stay as they were.

    python3 ogre02-arrival.py OUT_DIR        writes OUT_DIR/OGRE02.MAP (it replaces the disc's)
"""
import os
import sys
from mapbase import extracted, dwmap

WARP = 1
ORIGINAL = (-363, 942)
SPAWN = (-650, 1250)                                    # tile (43, 37): five tiles of open floor between the west wall and the box
MACHINEDRAMON = (-156, 1092)                            # D3 of the map
BODY = 250 + 100                                        # the Digimon's body box plus the tamer's


def repair(data):
    m = dwmap.MapFile(data)
    w = m.warps[WARP]
    if (w['x'], w['z']) != ORIGINAL:
        raise ValueError(f'OGRE02: exit {WARP} spawn is not the original one: {(w["x"], w["z"])}')
    w['x'], w['z'] = SPAWN
    return m.build()


def main(out):
    os.makedirs(out, exist_ok=True)
    with open(extracted('OGRE02') + '.MAP', 'rb') as f:
        data = repair(f.read())
    with open(os.path.join(out, 'OGRE02.MAP'), 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    main(sys.argv[1])
