# The Python view of script 187 of DG.SCN: screen 228 Back Dimension.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

dimension = screen(Screen.back_dimension_228)
tankmon0 = dimension.npc(Species.Tankmon, slot=0)
tankmon1 = dimension.npc(Species.Tankmon, slot=1)
golemon2 = dimension.npc(Species.Golemon, slot=2)
golemon3 = dimension.npc(Species.Golemon, slot=3)
t5 = text.s187.sec5
t6 = text.s187.sec6
t7 = text.s187.sec7
t8 = text.s187.sec8

@dimension.on_enter
def enter():    # section 254
    spawn_chest(Item.OffChip, at=(-412, 1068), opened=trigger(712), facing=2048)
    spawn_chest(Item.HPChip, at=(452, -446), opened=trigger(713), facing=1024)

@dimension.on_step(0)
def step0():    # section 51
    tamer.walk(2019, -420, wait=False)
    warp(Screen.back_dimension_227, entry=0)

@dimension.on_step(1)
def step1():    # section 52
    tamer.walk(-2797, 365, wait=False)
    if back_dimension_portal == 1:
        warp(Screen.ice_sanctuary_104, entry=0, then=60)
        return
    if back_dimension_portal == 2:
        warp(Screen.mansion_basement, entry=1, then=60)
        return
    if back_dimension_portal == 3:
        warp(Screen.ogre_fortress_47, entry=0, then=60)
        return

@tankmon0.on_talk
def talk():    # section 5
    recruitable(tankmon0, line=t5.u0)

@tankmon1.on_talk
def talk():    # section 6
    recruitable(tankmon1, line=t6.u0)

@golemon2.on_talk
def talk():    # section 7
    recruitable(golemon2, line=t7.u0)

@golemon3.on_talk
def talk():    # section 8
    recruitable(golemon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8)
