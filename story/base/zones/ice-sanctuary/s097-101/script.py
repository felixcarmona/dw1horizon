# The Python view of script 97 of DG.SCN: screen 101 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

sanctuary = screen(Screen.ice_sanctuary_101)
bluemeramon0 = sanctuary.npc(Species.BlueMeramon, slot=0)
bluemeramon1 = sanctuary.npc(Species.BlueMeramon, slot=1)
icemon2 = sanctuary.npc(Species.Icemon, slot=2)
icemon3 = sanctuary.npc(Species.Icemon, slot=3)
t5 = text.s097.sec5
t6 = text.s097.sec6
t7 = text.s097.sec7
t8 = text.s097.sec8

@sanctuary.on_enter
def enter():    # section 254
    spawn_chest(Item.Medicine, at=(79, 725), opened=trigger(665))

@sanctuary.on_step(0)
def step0():    # section 51
    tamer.walk(9, -3988, wait=False)
    warp(Screen.ice_sanctuary_100, entry=1)

@sanctuary.on_step(1)
def step1():    # section 52
    warp(Screen.ice_sanctuary_98, entry=3)

@sanctuary.on_step(2)
def step2():    # section 53
    warp(Screen.ice_sanctuary_99, entry=1)

@sanctuary.on_step(3)
def step3():    # section 54
    warp(Screen.ice_sanctuary_97, entry=2)

@sanctuary.on_step(4)
def step4():    # section 55
    warp(Screen.ice_sanctuary_102, entry=0)

@bluemeramon0.on_talk
def talk():    # section 5
    recruitable(bluemeramon0, line=t5.u0)

@bluemeramon1.on_talk
def talk():    # section 6
    recruitable(bluemeramon1, line=t6.u0)

@icemon2.on_talk
def talk():    # section 7
    recruitable(icemon2, line=t7.u0)

@icemon3.on_talk
def talk():    # section 8
    recruitable(icemon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 53, 54, 55, 5, 6, 7, 8)
