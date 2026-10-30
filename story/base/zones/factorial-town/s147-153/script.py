# The Python view of script 147 of DG.SCN: screen 153 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_153)
guardromon0 = town.npc(Species.Guardromon, slot=0)
guardromon1 = town.npc(Species.Guardromon, slot=1)
geremon2 = town.npc(Species.Geremon, slot=2)
geremon3 = town.npc(Species.Geremon, slot=3)
metalgreymonvirus = town.npc(Species.MetalGreymonVirus149, slot=4)
t5 = text.s147.sec5
t6 = text.s147.sec6
t7 = text.s147.sec7
t8 = text.s147.sec8
t9 = text.s147.sec9

@town.on_enter
def enter():    # section 254
    pass

@town.on_step(0)
def step0():    # section 51
    tamer.walk(1591, 607)
    tamer.walk(1593, -343, wait=False)
    warp(Screen.factorial_town_154, entry=0)

@guardromon0.on_talk
def talk():    # section 5
    recruitable(guardromon0, line=t5.u0)

@guardromon1.on_talk
def talk():    # section 6
    recruitable(guardromon1, line=t6.u0)

@geremon2.on_talk
def talk():    # section 7
    recruitable(geremon2, line=t7.u0)

@geremon3.on_talk
def talk():    # section 8
    recruitable(geremon3, line=t8.u0)

@metalgreymonvirus.on_talk
def talk():    # section 9
    say(t9.u0)
    if ask(yes=t9.m0.o0, no=t9.m0.o1):
        fight(metalgreymonvirus, escape=False)
        tamer.face(metalgreymonvirus)
        face(tamer)
        partner.face(metalgreymonvirus)
        tamer.arrived()
        say(t9.u1)
        walk_away(-3120, 1836, looks=3)
        leave()
        glances.set(0)
        sound(8, 10)
        narrator.say(t9.u2)
        engine.no_escape.clear()
        recruit(Species.MetalMamemon)
        engine.prosperity.add(3)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    say(t9.u3)
    walk_away(-3120, 1836, looks=3)
    leave()
    glances.set(0)
    return

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 8, 9)
