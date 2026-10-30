# The Python view of script 148 of DG.SCN: screen 154 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_154)
guardromon0 = town.npc(Species.Guardromon, slot=0)
platinumsukamon1 = town.npc(Species.PlatinumSukamon, slot=1)
platinumsukamon2 = town.npc(Species.PlatinumSukamon, slot=2)
geremon = town.npc(Species.Geremon, slot=3)
guardromon4 = town.npc(Species.Guardromon, slot=4)
guardromon5 = town.npc(Species.Guardromon, slot=5)
t10 = text.s148.sec10
t5 = text.s148.sec5
t6 = text.s148.sec6
t7 = text.s148.sec7
t8 = text.s148.sec8
t9 = text.s148.sec9

@town.on_enter
def enter():    # section 254
    pass

@town.on_step(0)
def step0():    # section 51
    tamer.walk(-3979, 875, wait=False)
    warp(Screen.factorial_town_153, entry=1)

@town.on_step(1)
def step1():    # section 52
    tamer.walk(3538, -555, wait=False)
    warp(Screen.factorial_town_155, entry=1)

@town.on_step(2)
def step2():    # section 53
    tamer.walk(1707, 1557, wait=False)
    warp(Screen.factorial_town_157, entry=0)

@town.on_step(3)
def step3():    # section 54
    warp(Screen.sewer_163, entry=0)

@guardromon0.on_talk
def talk():    # section 5
    recruitable(guardromon0, line=t5.u0)

@platinumsukamon1.on_talk
def talk():    # section 6
    recruitable(platinumsukamon1, line=t6.u0)

@platinumsukamon2.on_talk
def talk():    # section 7
    recruitable(platinumsukamon2, line=t7.u0)

@geremon.on_talk
def talk():    # section 8
    recruitable(geremon, line=t8.u0)

@guardromon4.on_talk
def talk():    # section 9
    recruitable(guardromon4, line=t9.u0)

@guardromon5.on_talk
def talk():    # section 10
    recruitable(guardromon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 53, 54, 5, 6, 7, 8, 9, 10)
