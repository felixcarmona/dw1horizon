# The Python view of script 59 of DG.SCN: screen 60 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

mansion = screen(Screen.grey_lords_mansion_60)

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_use(1)
def use1():    # section 81
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(-1400, 600, wait=False)
    warp(Screen.grey_lords_mansion_52, entry=1)

@mansion.on_use(2)
def use2():    # section 82
    sound(8, 10)
    wait(500)
    tamer.walk(800, -400, wait=False)
    warp(Screen.underground_lab_68, entry=0)
    return

# the section table, in the order of the original header
sections(254, 81, 82)
