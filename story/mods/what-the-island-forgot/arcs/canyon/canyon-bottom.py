# 42 and 368, the Great Canyon Bottom Area (script 42; maps/gcan07-crack.py): the crack in the ground (step trigger 1;
# section 51, trigger 0, is the game's landing after the fall from the top area). Before the Motor is broken (R1) the
# crack is not there (42 shows the player's own background, its step tiles do nothing); with R1 the ways in lead to 368,
# where the crack is open and leads down to the Descent.
from dw import *
from dw.base.great_canyon_bot_area_42 import area as bottom
from ...state import root1

@bottom.on_step(1, when=root1)
def down_the_crack():
    warp(303, entry=0)
