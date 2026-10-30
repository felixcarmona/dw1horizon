# The Python view of script 141 of DG.SCN: screen 147 Toy Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.toy_mansion_147)
t81 = text.s141.sec81

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_use(1)
def use1():    # section 81
    if toy_mansion_seal_lifted:
        tamer.walk(-56, 1454)
        wait(250)
        tamer.turn(2048)
        wait(250)
        swing_door(0)
        wait(1000)
        tamer.walk(-54, 2652, wait=False)
        warp(Screen.toy_mansion_148, entry=0)
    tamer.say(t81.u0)
    return

# the section table, in the order of the original header
sections(254, 81)
