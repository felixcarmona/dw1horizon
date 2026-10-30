# The Python view of script 171 of DG.SCN: screen 211 Item Keeper.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

keeper = screen(Screen.item_keeper)
agumon = keeper.npc(Species.Agumon, slot=0)
poyomon = keeper.npc(Species.Poyomon, slot=1)
t6 = text.s171.sec6
t81 = text.s171.sec81

@keeper.on_enter
def enter():    # section 254
    pass

@keeper.on_use(1)
def use1():    # section 81
    tamer.face(agumon)
    agumon.face(tamer)
    wait(250)
    if not item_keeper_intro_seen:
        item_keeper_intro_seen.set()
        agumon.say(t81.u0)
        return
    call(Routine.item_keeper, arg=5)

@poyomon.on_talk
def talk():    # section 6
    if engine.prosperity >= 30:
        say(t6.u0)
        return
    if engine.prosperity >= 15:
        say(t6.u1)
        return
    say(t6.u2)

@keeper.on_step(0)
def step0():    # section 51
    tamer.walk(123, -1391, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=3)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=3)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=3)
            warp(Screen.file_city_168, entry=3)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=3)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=3)
        warp(Screen.file_city_171, entry=3)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=3)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=3)
        warp(Screen.file_city_174, entry=3)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=3)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=3)
    warp(Screen.file_city_177, entry=3)

# the section table, in the order of the original header
sections(254, 81, 6, 51)
