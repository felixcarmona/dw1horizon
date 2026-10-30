# 41, the Great Canyon Bottom Area's first part: the way on (step trigger 0: the exit's tiles, maps/gcan06-way.py) to
# the second part: 42, or 368 with the crack open once the Motor is broken (R1).
from dw import *
from dw.base.great_canyon_bot_area_41 import area
from ...state import root1

@area.on_step(0, when=root1)
def to_the_open_crack():
    warp(368, entry=0)

@area.on_step(0, when=not root1)
def to_the_bottom():
    warp(Screen.great_canyon_bot_area_42, entry=0)
