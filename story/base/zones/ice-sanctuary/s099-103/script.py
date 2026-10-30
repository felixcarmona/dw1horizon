# The Python view of script 99 of DG.SCN: screen 103 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

sanctuary = screen(Screen.ice_sanctuary_103)
gururumon0 = sanctuary.npc(Species.Gururumon, slot=0)
gururumon1 = sanctuary.npc(Species.Gururumon, slot=1)
t5 = text.s099.sec5
t6 = text.s099.sec6

@sanctuary.on_enter
def enter():    # section 254
    spawn_chest(Item.OmniDisk, at=(-1698, -3442), opened=trigger(662), facing=3072)
    spawn_chest(Item.Omnipotent, at=(740, -2753), opened=trigger(663))

@sanctuary.on_step(0)
def step0():    # section 51
    tamer.walk(-2446, 1282, wait=False)
    warp(Screen.ice_sanctuary_98, entry=2)

@sanctuary.on_step(1)
def step1():    # section 52
    warp(Screen.freezeland_92, entry=1)

@sanctuary.on_step(2)
def step2():    # section 53
    warp(Screen.ice_sanctuary_100, entry=0)

@gururumon0.on_talk
def talk():    # section 5
    recruitable(gururumon0, line=t5.u0)

@gururumon1.on_talk
def talk():    # section 6
    recruitable(gururumon1, line=t6.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 53, 5, 6)
