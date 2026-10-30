# The Python view of script 146 of DG.SCN: screen 152 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_152)
guardromon0 = town.npc(Species.Guardromon, slot=0)
guardromon1 = town.npc(Species.Guardromon, slot=1)
platinumsukamon2 = town.npc(Species.PlatinumSukamon, slot=2)
platinumsukamon3 = town.npc(Species.PlatinumSukamon, slot=3)
whamon = town.npc(Species.Whamon146, slot=4)
t5 = text.s146.sec5
t6 = text.s146.sec6
t7 = text.s146.sec7
t8 = text.s146.sec8
t81 = text.s146.sec81

@town.on_enter
def enter():    # section 254
    pass

@town.on_step(0)
def step0():    # section 51
    pass

@guardromon0.on_talk
def talk():    # section 5
    recruitable(guardromon0, line=t5.u0)

@guardromon1.on_talk
def talk():    # section 6
    recruitable(guardromon1, line=t6.u0)

@platinumsukamon2.on_talk
def talk():    # section 7
    recruitable(platinumsukamon2, line=t7.u0)

@platinumsukamon3.on_talk
def talk():    # section 8
    recruitable(platinumsukamon3, line=t8.u0)

@town.on_use(1)
def use1():    # section 81
    tamer.face(whamon)
    whamon.say(t81.u0)
    if ask(yes=t81.m0.o0, no=t81.m0.o1):
        if not recruited(Species.Agumon):
            warp(Screen.file_city_204, entry=0)
        if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
            if not recruited(Species.Birdramon):
                if recruited(Species.Vegiemon):
                    warp(Screen.file_city_170, entry=0)
                if recruited(Species.Palmon):
                    warp(Screen.file_city_169, entry=0)
                warp(Screen.file_city_168, entry=0)
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_173, entry=0)
            if recruited(Species.Palmon):
                warp(Screen.file_city_172, entry=0)
            warp(Screen.file_city_171, entry=0)
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_176, entry=0)
            if recruited(Species.Palmon):
                warp(Screen.file_city_175, entry=0)
            warp(Screen.file_city_174, entry=0)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_179, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_178, entry=0)
        warp(Screen.file_city_177, entry=0)

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 8, 81)
