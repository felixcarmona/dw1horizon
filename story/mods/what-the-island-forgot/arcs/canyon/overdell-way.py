# The way into the Great Canyon Entrance from Overdell (screen 34), DGHA01's exit 2 (step trigger 0: the exit's tiles, maps/): screen 36,
# or 367, the same place with the stone bridge, once the Motor is broken (R1, maps/stone-bridge.py).
from dw import *
from dw.base.overdell import overdell
from ...state import root1

@overdell.on_step(0, when=root1)
def to_the_stone_bridge():
    warp(367, entry=2)

@overdell.on_step(0, when=not root1)
def to_the_canyon():
    warp(Screen.great_canyon_entrance, entry=2)
