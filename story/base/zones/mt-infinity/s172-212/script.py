# The Python view of script 172 of DG.SCN: screen 212 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

infinity = screen(Screen.mt_infinity_212)
vermilimon0 = infinity.npc(Species.Vermilimon, slot=0)
gururumon1 = infinity.npc(Species.Gururumon, slot=1)
vermilimon2 = infinity.npc(Species.Vermilimon, slot=2)
slot3 = infinity.npc(None, slot=3)    # the .MAP has Vermilimon here; the script spawns what stands here
gururumon4 = infinity.npc(Species.Gururumon, slot=4)
t5 = text.s172.sec5
t6 = text.s172.sec6
t7 = text.s172.sec7
t8 = text.s172.sec8
t9 = text.s172.sec9

@infinity.on_enter
def enter():    # section 254
    spawn_chest(Item.LargeMP, at=(3621, 1184), opened=trigger(684), facing=1024)

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(-1118, 1965, wait=False)
    warp(Screen.mt_infinity_219, entry=0)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(-260, 387, wait=False)
    warp(Screen.mt_infinity_210, entry=1)

@vermilimon0.on_talk
def talk():    # section 5
    recruitable(vermilimon0, line=t5.u0)

@gururumon1.on_talk
def talk():    # section 6
    recruitable(gururumon1, line=t6.u0)

@vermilimon2.on_talk
def talk():    # section 7
    recruitable(vermilimon2, line=t7.u0)

@slot3.on_talk
def talk():    # section 8
    recruitable(slot3, line=t8.u0, joins=Species.Vermilimon)

@gururumon4.on_talk
def talk():    # section 9
    recruitable(gururumon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9)
