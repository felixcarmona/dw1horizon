# The Python view of script 195 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lib = script(195)
golemon0 = lib.npc(Species.Golemon, slot=0)
golemon1 = lib.npc(Species.Golemon, slot=1)
golemon2 = lib.npc(Species.Golemon, slot=2)
t5 = text.s195.sec5
t6 = text.s195.sec6
t7 = text.s195.sec7

@lib.on_enter
def enter():    # section 254
    spawn_chest(Item.AutoPilot, at=(-2681, -404), opened=trigger(687), facing=2048)

@lib.on_step(0)
def step0():    # section 51
    tamer.walk(2133, -489, wait=False)
    warp(249, entry=0)

@lib.on_step(1)
def step1():    # section 52
    tamer.walk(2909, 268, wait=False)
    warp(247, entry=1)

@golemon0.on_talk
def talk():    # section 5
    recruitable(golemon0, line=t5.u0)

@golemon1.on_talk
def talk():    # section 6
    recruitable(golemon1, line=t6.u0)

@golemon2.on_talk
def talk():    # section 7
    recruitable(golemon2, line=t7.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7)
