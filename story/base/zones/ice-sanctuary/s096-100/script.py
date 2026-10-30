# The Python view of script 96 of DG.SCN: screen 100 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

sanctuary = screen(Screen.ice_sanctuary_100)
hyogamon0 = sanctuary.npc(Species.Hyogamon, slot=0)
hyogamon1 = sanctuary.npc(Species.Hyogamon, slot=1)
gururumon = sanctuary.npc(Species.Gururumon, slot=2)
t5 = text.s096.sec5
t6 = text.s096.sec6
t7 = text.s096.sec7

@sanctuary.on_enter
def enter():    # section 254
    pass

@sanctuary.on_step(0)
def step0():    # section 51
    warp(Screen.ice_sanctuary_99, entry=1)

@sanctuary.on_step(1)
def step1():    # section 52
    tamer.walk(-1991, 5542, wait=False)
    warp(Screen.ice_sanctuary_101, entry=0)

@hyogamon0.on_talk
def talk():    # section 5
    recruitable(hyogamon0, line=t5.u0)

@hyogamon1.on_talk
def talk():    # section 6
    recruitable(hyogamon1, line=t6.u0)

@gururumon.on_talk
def talk():    # section 7
    recruitable(gururumon, line=t7.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7)
