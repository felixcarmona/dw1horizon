# 44, the Great Canyon Top Area: the way down over the invisible bridge to the Great Canyon Entrance (step trigger 0;
# the game's own handler warps to 36): with the Motor broken (R1) it leads to 367, the same place with the stone bridge.
from dw import *
from dw.names import *
from dw.base.great_canyon_top_area_44 import area
from ...state import root1

@area.on_step(0, when=root1 and invisible_bridge_crossed)
def down_to_the_stone_bridge():
    tamer.walk(10000, -2800, wait=False)
    warp(367, entry=1)
