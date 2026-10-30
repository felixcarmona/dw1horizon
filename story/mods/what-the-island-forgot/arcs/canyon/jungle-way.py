# The way into the Great Canyon Entrance from Tropical Jungle (screen 14), TROP03's exit 0 (step trigger 1: the exit's tiles, maps/): screen 36,
# or 367, the same place with the stone bridge, once the Motor is broken (R1, maps/stone-bridge.py).
from dw import *
from dw.base.tropical_jungle_14 import jungle
from ...state import root1

@jungle.on_step(1, when=root1)
def to_the_stone_bridge():
    warp(367, entry=0)

@jungle.on_step(1, when=not root1)
def to_the_canyon():
    warp(Screen.great_canyon_entrance, entry=0)
