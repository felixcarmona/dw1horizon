# The Python view of script 152 of DG.SCN: screen 158 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_158)
geremon0 = town.npc(Species.Geremon, slot=0)
geremon1 = town.npc(Species.Geremon, slot=1)
guardromon2 = town.npc(Species.Guardromon, slot=2)
guardromon3 = town.npc(Species.Guardromon, slot=3)
guardromon4 = town.npc(Species.Guardromon, slot=4)
guardromon5 = town.npc(Species.Guardromon, slot=5)
t10 = text.s152.sec10
t5 = text.s152.sec5
t6 = text.s152.sec6
t7 = text.s152.sec7
t8 = text.s152.sec8
t9 = text.s152.sec9

@town.on_enter
def enter():    # section 254
    pass

@geremon0.on_talk
def talk():    # section 5
    recruitable(geremon0, line=t5.u0)

@geremon1.on_talk
def talk():    # section 6
    recruitable(geremon1, line=t6.u0)

@guardromon2.on_talk
def talk():    # section 7
    recruitable(guardromon2, line=t7.u0, joins=Species.Guardromon)

@guardromon3.on_talk
def talk():    # section 8
    recruitable(guardromon3, line=t8.u0)

@guardromon4.on_talk
def talk():    # section 9
    recruitable(guardromon4, line=t9.u0)

@guardromon5.on_talk
def talk():    # section 10
    recruitable(guardromon5, line=t10.u0)

@town.on_use(1)
def use1():    # section 81
    swing_door(1)
    sound(8, 2)
    wait(1000)
    tamer.walk(-1999, 800, wait=False)
    if trigger(329):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            warp(Screen.factorial_town_159, entry=0)
    warp(Screen.factorial_town_160, entry=0)

@town.on_use(2)
def use2():    # section 82
    swing_door(0)
    sound(8, 2)
    wait(1000)
    tamer.walk(683, 4120, wait=False)
    warp(Screen.factorial_town_162, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81, 82)
