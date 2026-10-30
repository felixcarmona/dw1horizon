# The Python view of script 196 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lib = script(196)
gururumon0 = lib.npc(Species.Gururumon, slot=0)
gururumon1 = lib.npc(Species.Gururumon, slot=1)
vermilimon2 = lib.npc(Species.Vermilimon, slot=2)
vermilimon3 = lib.npc(Species.Vermilimon, slot=3)
t5 = text.s196.sec5
t6 = text.s196.sec6
t7 = text.s196.sec7
t8 = text.s196.sec8

@lib.on_enter
def enter():    # section 254
    spawn_chest(Item.DoubleFlop, at=(-2816, 318), opened=trigger(688), facing=3072)

@lib.on_step(0)
def step0():    # section 51
    tamer.walk(2759, 254, wait=False)
    warp(253, entry=0)

@lib.on_step(1)
def step1():    # section 52
    tamer.walk(-1123, -532, wait=False)
    warp(248, entry=0)

@gururumon0.on_talk
def talk():    # section 5
    recruitable(gururumon0, line=t5.u0)

@gururumon1.on_talk
def talk():    # section 6
    recruitable(gururumon1, line=t6.u0)

@vermilimon2.on_talk
def talk():    # section 7
    recruitable(vermilimon2, line=t7.u0)

@vermilimon3.on_talk
def talk():    # section 8
    recruitable(vermilimon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8)
