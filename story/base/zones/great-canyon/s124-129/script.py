# The Python view of script 124 of DG.SCN: screen 129 Great Canyon.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

canyon = screen(Screen.great_canyon_129)
slot0 = canyon.npc(None, slot=0)    # the .MAP has Birdramon143 here; the script spawns what stands here
t51 = text.s124.sec51
t81 = text.s124.sec81

@canyon.on_enter
def enter():    # section 254
    pass

@canyon.on_step(0)
def step0():    # section 51
    if recruited(Species.Birdramon):
        return
    wait(1000)
    tamer.walk(-142, -455, camera=True, wait=False)
    partner.walk(421, -421, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(1000)
    tamer.walk(58, -920, camera=True, wait=False)
    partner.walk(-142, -455, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(1000)
    tamer.walk(578, -695, wait=False)
    partner.walk(58, -920, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(1000)
    tamer.walk(615, -211, wait=False)
    partner.walk(578, -695, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(1000)
    tamer.play(16)
    tamer.say(t51.u0)
    wait(1000)
    tamer.face(partner)
    partner.face(tamer)
    tamer.arrived()
    partner.arrived()
    tamer.play(19)
    wait(750)
    tamer.say(t51.u1)
    tamer.play(anim.idle)
    tamer.play(24)
    wait(250)
    sound(8, 13)
    wait(1000)
    tamer.say(t51.u2)
    spawn(Species.Birdramon143, slot=0)
    wait(500)
    camera.on(slot0, speed=10)
    camera.arrived()
    slot0.run(278, -490, camera=True)
    camera.to(-83, -1182, speed=20)
    camera.arrived()
    tamer.face(slot0)
    slot0.face(tamer)
    partner.face(slot0)
    wait(1000)
    fight(slot0, escape=False)
    tamer.face(slot0)
    slot0.face(tamer)
    partner.face(slot0)
    wait(1000)
    slot0.play(28)
    wait(2000)
    slot0.say(t51.u3)
    tamer.say(t51.u4)
    slot0.say(t51.u5)
    tamer.play(20)
    tamer.say(t51.u6)
    tamer.play(anim.idle)
    slot0.say(t51.u7)
    tamer.say(t51.u8)
    slot0.say(t51.u9)
    tamer.say(t51.u10)
    slot0.say(t51.u11)
    tamer.play(16)
    tamer.say(t51.u12)
    slot0.say(t51.u13)
    tamer.play(19)
    tamer.say(t51.u14)
    slot0.say(t51.u15)
    slot0.walk(167, -665)
    camera.on(slot0, speed=20)
    camera.arrived()
    tamer.walk(367, -815, wait=False)
    partner.walk(437, -445, wait=False)
    tamer.arrived()
    partner.arrived()
    slot0.face(tamer)
    wait(250)
    sound(8, 10)
    narrator.say(t51.u16)
    recruit(Species.Birdramon)
    engine.prosperity.add(2)
    slot0.play(29)
    wait(2000)
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

@canyon.on_step(1)
def step1():    # section 52
    sound(8, 5)

@canyon.on_use(1)
def use1():    # section 81
    tamer.turn(1271)
    narrator.say(t81.u0)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            sound(8, 4)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            sound(8, 5)
            warp(Screen.great_canyon_top_area_38, entry=2, then=55)
            return
        case "b":
            hide_hud()
            if not canyon_elevator_unjammed:
                tamer.say(t81.u1)
                return
            sound(8, 4)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            sound(8, 5)
            warp(Screen.great_canyon_bot_area_41, entry=2, then=53)
            return
    return

# the section table, in the order of the original header
sections(254, 51, 52, 81)
