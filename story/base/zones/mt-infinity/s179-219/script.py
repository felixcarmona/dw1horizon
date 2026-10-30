# The Python view of script 179 of DG.SCN: screen 219 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

infinity = screen(Screen.mt_infinity_219)
vermilimon = infinity.npc(Species.Vermilimon, slot=0)
golemon1 = infinity.npc(Species.Golemon, slot=1)
golemon2 = infinity.npc(Species.Golemon, slot=2)
t5 = text.s179.sec5
t6 = text.s179.sec6
t7 = text.s179.sec7

@infinity.on_enter
def enter():    # section 254
    spawn_chest(Item.MPChip, at=(-1132, -422), opened=trigger(685), facing=3072)

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(439, -1204, wait=False)
    warp(247, entry=0)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(444, 2699, wait=False)
    warp(Screen.mt_infinity_212, entry=1)

@vermilimon.on_talk
def talk():    # section 5
    recruitable(vermilimon, line=t5.u0)

@golemon1.on_talk
def talk():    # section 6
    recruitable(golemon1, line=t6.u0)

@golemon2.on_talk
def talk():    # section 7
    recruitable(golemon2, line=t7.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7)
