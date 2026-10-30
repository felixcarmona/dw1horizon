# The Python view of script 47 of DG.SCN: screen 47 Ogre Fortress.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

fortress = screen(Screen.ogre_fortress_47)
agumon0 = fortress.npc(Species.Agumon, slot=0)
agumon1 = fortress.npc(Species.Agumon, slot=1)
agumon2 = fortress.npc(Species.Agumon, slot=2)
machinedramon = fortress.npc(Species.Machinedramon, slot=3)
analogman = fortress.npc(Species.Analogman, slot=4)
slot5 = fortress.npc(None, slot=5)    # the .MAP has Muchomon here; the script spawns what stands here
t5 = text.s047.sec5
t6 = text.s047.sec6
t60 = text.s047.sec60
t7 = text.s047.sec7

@fortress.on_enter
def enter():    # section 254
    pass

@agumon0.on_talk
def talk():    # section 5
    say(t5.u0)
    agumon1.run(-230, 547, wait=False)
    agumon2.run(483, 70, wait=False)
    agumon1.arrived()
    agumon2.arrived()
    wait(500)
    engine.no_escape.set()
    fight(agumon0, agumon1, agumon2)
    engine.no_escape.clear()
    run(550, -2050, wait=False)
    agumon1.run(550, -2050, wait=False)
    agumon2.run(550, -2050, wait=False)
    arrived()
    agumon1.arrived()
    agumon2.arrived()
    leave()
    agumon1.leave()
    agumon2.leave()
    camera.on(tamer, speed=10)
    camera.arrived()

@agumon1.on_talk
def talk():    # section 6
    say(t6.u0)
    agumon0.run(-815, 312, wait=False)
    agumon2.run(686, 312, wait=False)
    agumon0.arrived()
    agumon2.arrived()
    wait(500)
    engine.no_escape.set()
    fight(agumon0, agumon1, agumon2)
    engine.no_escape.clear()
    agumon0.run(550, -2050, wait=False)
    run(550, -2050, wait=False)
    agumon2.run(550, -2050, wait=False)
    agumon0.arrived()
    arrived()
    agumon2.arrived()
    agumon0.leave()
    leave()
    agumon2.leave()
    camera.on(tamer, speed=10)
    camera.arrived()

@agumon2.on_talk
def talk():    # section 7
    say(t7.u0)
    agumon1.run(702, 855, wait=False)
    agumon0.run(29, 586)
    agumon1.arrived()
    wait(500)
    engine.no_escape.set()
    fight(agumon0, agumon1, agumon2)
    engine.no_escape.clear()
    agumon0.run(550, -2050, wait=False)
    agumon1.run(550, -2050, wait=False)
    run(550, -2050, wait=False)
    agumon0.arrived()
    agumon1.arrived()
    arrived()
    agumon0.leave()
    agumon1.leave()
    leave()
    camera.on(tamer, speed=10)
    camera.arrived()

@fortress.on_step(9)
def step9():    # section 60
    wait(2000)
    camera.to(-200, 320, speed=20)
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
    fight(machinedramon, escape=False)
    machinedramon.walk(-156, 1092)
    machinedramon.play(43)
    wait(2000)
    tamer.say(t60.u4)
    tamer.face(machinedramon)
    machinedramon.arrived()
    tamer.arrived()
    machinedramon.leave()
    tamer.say(t60.u5)
    load(Species.Muchomon)
    spawn(Species.Muchomon, slot=5)
    slot5.say(t60.u6)
    slot5.face(tamer)
    wait(1000)
    slot5.say(t60.u7)
    recruit(Species.Koromon)
    back_dimension_portal.set(0)
    recruit(Species.Yuramon)
    days_since_passed_out.set(0)
    slot5.walk_away(320, -1546, looks=3)
    slot5.leave()
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
sections(254, 5, 6, 7, 60)
