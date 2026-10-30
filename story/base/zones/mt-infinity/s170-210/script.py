# The Python view of script 170 of DG.SCN: screen 210 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

infinity = screen(Screen.mt_infinity_210)
golemon = infinity.npc(Species.Golemon, slot=0)
piddomon1 = infinity.npc(Species.Piddomon, slot=1)
slot2 = infinity.npc(None, slot=2)    # the .MAP has Golemon here; the script spawns what stands here
piddomon3 = infinity.npc(Species.Piddomon, slot=3)
piddomon4 = infinity.npc(Species.Piddomon, slot=4)
t5 = text.s170.sec5
t6 = text.s170.sec6
t7 = text.s170.sec7
t8 = text.s170.sec8
t9 = text.s170.sec9

@infinity.on_enter
def enter():    # section 254
    spawn_chest(Item.Omnipotent, at=(474, 444), opened=trigger(682), facing=3072)

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(2989, 2649, wait=False)
    warp(Screen.mt_infinity_212, entry=0)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(-2579, -427, wait=False)
    warp(Screen.mt_infinity_167, entry=0)

@golemon.on_talk
def talk():    # section 5
    recruitable(golemon, line=t5.u0)

@piddomon1.on_talk
def talk():    # section 6
    recruitable(piddomon1, line=t6.u0)

@slot2.on_talk
def talk():    # section 7
    recruitable(slot2, line=t7.u0, joins=Species.Golemon)

@piddomon3.on_talk
def talk():    # section 8
    recruitable(piddomon3, line=t8.u0)

@piddomon4.on_talk
def talk():    # section 9
    recruitable(piddomon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9)
