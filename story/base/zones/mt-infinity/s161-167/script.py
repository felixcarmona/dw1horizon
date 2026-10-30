# The Python view of script 161 of DG.SCN: screen 167 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

infinity = screen(Screen.mt_infinity_167)
piddomon0 = infinity.npc(Species.Piddomon, slot=0)
piddomon1 = infinity.npc(Species.Piddomon, slot=1)
gururumon2 = infinity.npc(Species.Gururumon, slot=2)
piddomon3 = infinity.npc(Species.Piddomon, slot=3)
gururumon4 = infinity.npc(Species.Gururumon, slot=4)
t5 = text.s161.sec5
t6 = text.s161.sec6
t7 = text.s161.sec7
t8 = text.s161.sec8
t9 = text.s161.sec9

@infinity.on_enter
def enter():    # section 254
    spawn_chest(Item.LargeMP, at=(439, -429), opened=trigger(681), facing=3072)

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(1178, 1101, wait=False)
    warp(Screen.mt_infinity_166, entry=1)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(-405, 276, wait=False)
    warp(Screen.mt_infinity_210, entry=0)

@piddomon0.on_talk
def talk():    # section 5
    recruitable(piddomon0, line=t5.u0)

@piddomon1.on_talk
def talk():    # section 6
    recruitable(piddomon1, line=t6.u0)

@gururumon2.on_talk
def talk():    # section 7
    recruitable(gururumon2, line=t7.u0)

@piddomon3.on_talk
def talk():    # section 8
    recruitable(piddomon3, line=t8.u0)

@gururumon4.on_talk
def talk():    # section 9
    recruitable(gururumon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9)
