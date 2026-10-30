# The Python view of script 57 of DG.SCN: screen 58 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

mansion = screen(Screen.grey_lords_mansion_58)
tsukaimon = mansion.npc(Species.Tsukaimon, slot=0)
t5 = text.s057.sec5

@mansion.on_enter
def enter():    # section 254
    pass

@tsukaimon.on_talk
def talk():    # section 5
    recruitable(tsukaimon, line=t5.u0)

@mansion.on_use(1)
def use1():    # section 81
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(-1400, 300, wait=False)
    warp(Screen.grey_lords_mansion_57, entry=3)
    return

# the section table, in the order of the original header
sections(254, 5, 81)
