# The Python view of script 165 of DG.SCN: screen 205 Jijimon's house.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

house = screen(Screen.jijimons_house_205)
jijimon = house.npc(Species.Jijimon, slot=0)
angemon = house.npc(Species.Angemon142, slot=1)
tokomon = house.npc(Species.Tokomon, slot=2)
t20 = text.s165.sec20
t5 = text.s165.sec5
t7 = text.s165.sec7
t85 = text.s165.sec85

@house.on_enter
def enter():    # section 254
    pass

@house.on_step(3)
def step3():    # section 54
    jump_to_script(193, 55)

@jijimon.on_talk
def talk():    # section 5
    if not recruited(Species.Koromon) and not recruited(Species.Punimon) and back_dimension_portal != 0:
        if recruited(Species.Botamon) and recruited(Species.Yuramon):
            say(t5.u0)
            tamer.say(t5.u1)
            say(t5.u2)
            tamer.say(t5.u3)
            say(t5.u4)
            if not recruited(Species.Agumon):
                return
            jump_to_script(210, 51)
    if recruited(Species.Koromon) and not recruited(Species.Punimon):
        say(t5.u5)
        tamer.say(t5.u6)
        say(t5.u7)
        tamer.say(t5.u8)
        say(t5.u9)
        tamer.say(t5.u10)
        give(Item.ChainMelon)
        if engine.item_did_not_fit:
            if has(Item.SpikeClub, 99):
                return
            tamer.say(t5.u11)
            pick_item()
            take_picked(all=True)
            give(Item.ChainMelon)
        tamer.say(t5.u12)
        days_since_passed_out.set(0)
        recruit(Species.Punimon)
        return
    if engine.game_beaten and not recruited(Species.Botamon):
        say(t5.u13)
        tamer.say(t5.u14)
        say(t5.u15)
        tamer.say(t5.u16)
        say(t5.u17)
        recruit(Species.Botamon)
    if not recruited(Species.Agumon):
        return
    jump_to_script(210, 51)

@angemon.on_talk
def talk():    # section 6
    jump_to_script(211, 8)

@house.section(20)
def sec20():    # section 20
    camera.to(183, 221, speed=20)
    camera.arrived()
    wait(1000)
    partner.add(hp=9999)
    partner.add(mp=9999)
    engine.no_escape.clear()
    jijimon.play(29)
    wait(250)
    jijimon.say(t20.u0)
    jijimon.play(anim.idle)

@house.on_step(20)
def step20():    # section 71
    jump_to_script(212, 71)

@house.on_step(21)
def step21():    # section 72
    jump_to_script(212, 72)

@house.on_step(22)
def step22():    # section 73
    jump_to_script(212, 73)

@house.on_use(5)
def use5():    # section 85
    if not save_machine_explained:
        save_machine_explained.set()
        tamer.say(t85.u0)
        jijimon.face(tamer)
        tamer.face(jijimon)
        wait(250)
        jijimon.say(t85.u1)
        tamer.turn(0)
        wait(250)
        return
    narrator.say(t85.u2)
    match narrator.choose(a=t85.m0.o0, b=t85.m0.o1):
        case "a":
            hide_hud()
            call(Routine.save_machine)
            return
        case "b":
            return
        case _:
            return

@tokomon.on_talk
def talk():    # section 7
    if not recruited(Species.Whamon) and ogre_fortress_cleared:
        say(t7.u0)
        return
    if invisible_bridge_rumor_heard and invisible_bridge_crossed:
        say(t7.u1)
        return
    if engine.prosperity >= 6:
        say(t7.u2)
        return
    say(t7.u3)

@house.on_step(0)
def step0():    # section 51
    tamer.walk(-470, -1970, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=2)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=2)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=2)
            warp(Screen.file_city_168, entry=2)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=2)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=2)
        warp(Screen.file_city_171, entry=2)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=2)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=2)
        warp(Screen.file_city_174, entry=2)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=2)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=2)
    warp(Screen.file_city_177, entry=2)

# the section table, in the order of the original header
sections(254, 54, 5, 6, 20, 71, 72, 73, 85, 7, 51)
