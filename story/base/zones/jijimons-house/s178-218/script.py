# The Python view of script 178 of DG.SCN: screen 218 Jijimon's house.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

house = screen(Screen.jijimons_house)
jijimon = house.npc(Species.Jijimon, slot=0)
tokomon = house.npc(Species.Tokomon, slot=1)
botamon = house.npc(Species.Botamon, slot=2)
t20 = text.s178.sec20
t5 = text.s178.sec5
t6 = text.s178.sec6
t7 = text.s178.sec7
t82 = text.s178.sec82
t85 = text.s178.sec85

@house.on_enter
def enter():    # section 254
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        objects[7].show()
    if recruited(Species.Agumon):
        objects[8].show()
    else:
        raw.set_rect_impassable(0, 40, 38, 2, 2)

@house.on_step(3)
def step3():    # section 54
    jump_to_script(193, 55)

@jijimon.on_talk
def talk():    # section 5
    if not recruited(Species.Koromon) and not recruited(Species.Punimon) and back_dimension_portal != 0 and recruited(Species.Botamon) and recruited(Species.Yuramon):
        say(t5.u0)
        tamer.say(t5.u1)
        say(t5.u2)
        tamer.say(t5.u3)
        say(t5.u4)
    else:
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
    if recruited(Species.Agumon):
        jump_to_script(210, 51)
    if debug_test_npcs:
        return tokomon.talk()
    play(anim.idle)
    play(29)
    wait(250)
    say(t5.u18)
    play(anim.idle)
    play(29)
    wait(250)
    say(t5.u19)
    play(anim.idle)
    play(29)
    wait(250)
    say(t5.u20)
    play(anim.idle)

@tokomon.on_talk
def talk():    # section 6
    if not starter_items_given:
        if not coela_point_crossing_done and underground_pond_dig_work < 10:
            say(t6.u0)
            narrator.say(t6.u1)
            give(Item.SmRecovery, 3)
            give(Item.Meat, 3)
            give(Item.MPFloppy, 3)
            give(Item.Restore)
            give(Item.Bandage, 2)
            give(Item.Medicine)
            say(t6.u2)
            starter_items_given.set()
            return
    if not recruited(Species.Whamon) and ogre_fortress_cleared:
        say(t6.u3)
        return
    if invisible_bridge_rumor_heard and invisible_bridge_crossed:
        say(t6.u4)
        return
    if engine.prosperity >= 6:
        say(t6.u5)
        return
    say(t6.u6)

@botamon.on_talk
def talk():    # section 7
    if not debug_mode:
        jump_to_script(209, 5)
    roll = random.roll(2)
    if engine.prosperity >= 3 and roll == 0:
        say(t7.u0)
        return
    if engine.prosperity >= 3 and roll == 1:
        say(t7.u1)
        return
    if engine.prosperity >= 3 and roll == 2:
        say(t7.u2)
        return
    say(t7.u3)

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

@house.on_use(2)
def use2():    # section 82
    tamer.turn(3072)
    wait(250)
    sound(0, 0)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        tamer.say(t82.u0)
    else:
        narrator.say(t82.u1)
    match choose(a=t82.m0.o0, b=t82.m0.o1):
        case "a":
            raw.store_date(date_year)
            raw.add_minutes_to_date_at(date_year, 60)
            raw.advance_to_date_at(date_year)
            partner.add(hp=300)
            partner.add(mp=300)
            partner.sub(tiredness=10)
            warp(Screen.jijimons_house, entry=2)
            return
        case "b":
            sound(0, 1)
            return
        case _:
            sound(0, 1)
            return

@house.on_use(3)
def use3():    # section 83
    if recruited(Species.Agumon):
        return
    tamer.turn(3072)
    wait(250)
    jump_to_script(220, 83)

@house.on_use(4)
def use4():    # section 84
    if recruited(Species.Agumon):
        return
    tamer.turn(1024)
    wait(250)
    jump_to_script(220, 83)

@house.on_use(6)
def use6():    # section 86
    if recruited(Species.Agumon):
        return
    tamer.turn(2048)
    wait(250)
    jump_to_script(220, 83)

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
sections(254, 54, 5, 6, 7, 20, 71, 72, 73, 85, 82, 83, 84, 86, 51)
