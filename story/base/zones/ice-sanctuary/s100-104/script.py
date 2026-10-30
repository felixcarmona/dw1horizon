# The Python view of script 100 of DG.SCN: screen 104 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sanctuary = screen(Screen.ice_sanctuary_104)
machinedramon = sanctuary.npc(Species.Machinedramon, slot=0)
analogman = sanctuary.npc(Species.Analogman, slot=1)
slot2 = sanctuary.npc(None, slot=2)    # the .MAP has SnowAgumon here; the script spawns what stands here
t60 = text.s100.sec60

@sanctuary.on_enter
def enter():    # section 254
    pass

@sanctuary.on_step(9)
def step9():    # section 60
    wait(2000)
    camera.to(0, 1000, speed=20)
    tamer.play(15)
    wait(1000)
    tamer.say(t60.u0)
    analogman.say(t60.u1)
    tamer.say(t60.u2)
    analogman.arrived()
    analogman.leave()
    wait(1000)
    tamer.say(t60.u3)
    machinedramon.play(28)
    wait(2000)
    wait(2000)
    fight(machinedramon, escape=False)
    machinedramon.walk(0, 950)
    machinedramon.play(43)
    wait(2000)
    tamer.say(t60.u4)
    tamer.face(machinedramon)
    machinedramon.arrived()
    tamer.arrived()
    machinedramon.leave()
    tamer.say(t60.u5)
    load(Species.SnowAgumon)
    spawn(Species.SnowAgumon, slot=2)
    slot2.say(t60.u6)
    slot2.face(tamer)
    wait(1000)
    slot2.say(t60.u7)
    recruit(Species.Koromon)
    back_dimension_portal.set(0)
    recruit(Species.Yuramon)
    days_since_passed_out.set(0)
    slot2.walk_away(3050, 950, looks=3)
    slot2.leave()
    glances.set(0)
    tamer.play(16)
    wait(2000)
    tamer.say(t60.u8)
    wait(1000)
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
sections(254, 60)
