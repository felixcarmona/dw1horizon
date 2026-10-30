# The Python view of script 160 of DG.SCN: screen 166 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

infinity = screen(Screen.mt_infinity_166)
vermilimon0 = infinity.npc(Species.Vermilimon, slot=0)
vermilimon1 = infinity.npc(Species.Vermilimon, slot=1)
golemon2 = infinity.npc(Species.Golemon, slot=2)
vermilimon3 = infinity.npc(Species.Vermilimon, slot=3)
golemon4 = infinity.npc(Species.Golemon, slot=4)
t5 = text.s160.sec5
t6 = text.s160.sec6
t7 = text.s160.sec7
t8 = text.s160.sec8
t9 = text.s160.sec9

@infinity.on_enter
def enter():    # section 254
    spawn_chest(Item.OmniDisk, at=(-2663, 277), opened=trigger(680), facing=3072)

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(2099, -558, wait=False)
    warp(Screen.mt_infinity_167, entry=1)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(-1958, 2679, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=0)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=9)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=9)
            warp(Screen.file_city_168, entry=9)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=9)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=9)
        warp(Screen.file_city_171, entry=9)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=9)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=9)
        warp(Screen.file_city_174, entry=9)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=9)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=9)
    warp(Screen.file_city_177, entry=9)

@vermilimon0.on_talk
def talk():    # section 5
    recruitable(vermilimon0, line=t5.u0)

@vermilimon1.on_talk
def talk():    # section 6
    recruitable(vermilimon1, line=t6.u0)

@golemon2.on_talk
def talk():    # section 7
    recruitable(golemon2, line=t7.u0)

@vermilimon3.on_talk
def talk():    # section 8
    recruitable(vermilimon3, line=t8.u0)

@golemon4.on_talk
def talk():    # section 9
    recruitable(golemon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9)
