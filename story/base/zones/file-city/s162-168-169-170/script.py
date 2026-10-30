# The Python view of script 162 of DG.SCN: screen 168 File City, screen 169 File City, screen 170 File City, screen 171 File City, screen 172 File City, screen 173 File City, screen 174 File City, screen 175 File City, screen 176 File City, screen 177 File City, screen 178 File City, screen 179 File City.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

city_168 = screen(Screen.file_city_168)
city_169 = screen(Screen.file_city_169)
city_170 = screen(Screen.file_city_170)
city_171 = screen(Screen.file_city_171)
city_172 = screen(Screen.file_city_172)
city_173 = screen(Screen.file_city_173)
city_174 = screen(Screen.file_city_174)
city_175 = screen(Screen.file_city_175)
city_176 = screen(Screen.file_city_176)
city_177 = screen(Screen.file_city_177)
city_178 = screen(Screen.file_city_178)
city_179 = screen(Screen.file_city_179)
yuramon = city_168.npc(Species.Yuramon, slot=0)
sukamon = city_168.npc(Species.Sukamon159, slot=1)
andromon = city_168.npc(Species.Andromon160, slot=2)
kokatorimon = city_168.npc(Species.Kokatorimon168, slot=3)
slot4 = city_168.npc(None, slot=4)    # the .MAP has Greymon129 here; the script spawns what stands here
slot5 = city_168.npc(None, slot=5)    # the .MAP has Airdramon131 here; the script spawns what stands here
slot6 = city_168.npc(None, slot=6)    # the .MAP has Tanemon here; the script spawns what stands here
whamon = city_168.npc(Species.Whamon146, slot=7)
t254 = text.s162.sec254
t5 = text.s162.sec5
t55 = text.s162.sec55
t57 = text.s162.sec57
t6 = text.s162.sec6
t7 = text.s162.sec7
t8 = text.s162.sec8
t81 = text.s162.sec81
t82 = text.s162.sec82
t83 = text.s162.sec83

@city_168.on_enter
def enter():    # section 254
    if recruited(Species.Koromon) and recruited(Species.Punimon) and days_since_passed_out >= 20:
        unrecruit(Species.Koromon)
        unrecruit(Species.Punimon)
        raw.store_random(back_dimension_portal, 2)
        if back_dimension_portal == 0:
            back_dimension_portal.set(3)
            chest_back_dimension.ray_gun.clear()
            chest_back_dimension.quick_chip.clear()
            chest_back_dimension.mp_chip.clear()
            chest_back_dimension.def_chip.clear()
            chest_back_dimension.brain_chip.clear()
            chest_back_dimension.off_chip.clear()
            chest_back_dimension.hp_chip.clear()
    call(Routine.save_clock_speed, arg=0)
    tamerless_battle.clear()
    if drill_tunnel_progress >= 3:
        underground_pond_dig_work.add(1)
    if drill_tunnel_progress >= 1:
        drill_tunnel_progress.set(1)
    if clock.day != 14:
        rain_plant_picked.clear()
    if engine.game_beaten and not ending_homecoming_seen:
        raw.entity_move_to(partner, 302, -2961, 5, 0)
        partner.arrived()
        partner.turn(2048)
        wait(2000)
        tamer.say(t254.u0)
        tamer.play(anim.tamer_victory)
        wait(1000)
        tamer.face(partner)
        wait(250)
        tamer.say(t254.u1)
        tamer.play(anim.offer_item)
        wait(500)
        partner.play(11)
        wait(2000)
        ending_homecoming_seen.set()
        camera.on(tamer, speed=10)
        camera.arrived()
        if tamer.level != 10:
            tamer.add(level=1)
            narrator.say(t254.u2)
        medal.ending.set()
        sound(0, 7)
        narrator.say(t254.u3)
        raw.give_card(65)
        narrator.say(t254.u4)
    if recruited(Species.Drimogemon):
        objects[0].hide()
        objects[1].hide()
        objects[2].hide()
    if recruited(Species.Whamon):
        objects[3].hide()
        objects[4].hide()
        objects[5].hide()
        objects[6].hide()
        objects[7].hide()
        objects[8].hide()
        objects[9].hide()
        objects[10].hide()
        objects[11].hide()
        objects[12].hide()
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        objects[13].hide()
        objects[14].hide()
        objects[15].hide()
        objects[16].hide()
        objects[17].hide()
        objects[18].hide()
        objects[19].hide()
        objects[20].hide()
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        objects[21].hide()
        objects[22].hide()
        objects[23].hide()
        objects[24].hide()
        objects[25].hide()
        objects[26].hide()
    if recruited(Species.Kokatorimon):
        objects[27].hide()
        objects[28].hide()
        objects[29].hide()
        objects[30].hide()
        objects[31].hide()
        objects[32].hide()
        raw.set_rect_impassable(0, 33, 69, 3, 2)
    if clock.hour < 7 and clock.hour >= 19:
        if recruited(Species.Kokatorimon):
            objects[59].hide()
            objects[60].hide()
            objects[61].hide()
            objects[62].hide()
        if recruited(Species.Angemon) or recruited(Species.Monzaemon) or engine.prosperity >= 50:
            if recruited(Species.Elecmon):
                objects[63].hide()
                objects[64].hide()
                objects[65].hide()
                objects[66].hide()
                objects[67].hide()
    if recruited(Species.Palmon):
        objects[68].hide()
        objects[69].hide()
        objects[70].hide()
    if recruited(Species.Vegiemon):
        objects[71].hide()
    if recruited(Species.Palmon) and date_day == 14 and not rain_plant_picked:
        objects[72].hide()
    if mt_infinity_entrance_found:
        objects[73].show()
        objects[74].show()
        objects[75].show()
        objects[76].show()
        objects[77].show()
        objects[78].show()
        objects[79].hide()
        objects[80].hide()
        objects[81].hide()
        objects[82].hide()
        objects[83].hide()

@city_168.on_step(0)
def step0():    # section 51
    tamer.walk(250, -5000, wait=False)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=1)
                    return
                warp(Screen.file_city_191, entry=1)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=1)
                return
            warp(Screen.file_city_190, entry=1)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=1)
                return
            warp(Screen.file_city_194, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=1)
            return
        warp(Screen.file_city_189, entry=1)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=1)
                    return
                warp(Screen.file_city_183, entry=1)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=1)
                return
            warp(Screen.file_city_182, entry=1)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=1)
                return
            warp(Screen.file_city_186, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=1)
            return
        warp(Screen.file_city_181, entry=1)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=1)
                return
            warp(Screen.file_city_198, entry=1)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=1)
            return
        warp(Screen.file_city_197, entry=1)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=1)
            return
        warp(Screen.file_city_201, entry=1)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=1)
        return
    warp(Screen.file_city_180, entry=1)
    return

@yuramon.on_talk
def talk():    # section 5
    if not recruited(Species.Seadramon) and engine.prosperity >= 40 and not recruited(Species.Whamon) and ogre_fortress_cleared:
        if not recruited(Species.Kokatorimon):
            say(t5.u0)
            return
    if not recruited(Species.Kokatorimon) and engine.prosperity >= 25 and not recruited(Species.Whamon) and ogre_fortress_cleared:
        say(t5.u1)
        return
    if not recruited(Species.Whamon) and ogre_fortress_cleared:
        say(t5.u2)
        return
    if not ogre_fortress_cleared and canyon_bandits_beaten:
        say(t5.u3)
        return
    if not canyon_bandits_beaten and invisible_bridge_crossed:
        canyon_bandits_active.set()
        say(t5.u4)
        tamer.say(t5.u5)
        say(t5.u6)
        tamer.say(t5.u7)
        return
    if engine.prosperity >= 6:
        invisible_bridge_rumor_heard.set()
        say(t5.u8)
        return
    if engine.game_beaten and not recruited(Species.Koromon):
        say(t5.u9)
        return
    if engine.game_beaten and recruited(Species.Koromon):
        say(t5.u10)
        return
    say(t5.u11)

@sukamon.on_talk
def talk():    # section 6
    say(t6.u0)

@andromon.on_talk
def talk():    # section 7
    say(t7.u0)

@kokatorimon.on_talk
def talk():    # section 8
    if not city_resident_met.kokatorimon:
        city_resident_met.kokatorimon.set()
        say(t8.u0)
        return
    say(t8.u1)

@slot6.on_talk
def talk():    # section 11
    jump_to_script(207, 11)

@city_168.on_use(1)
def use1():    # section 81
    if not recruited(Species.Palmon):
        return
    raw.set_textbox_origin(944, 0, 1158)
    if recruited(Species.Vegiemon) and clock.hour >= 7 and clock.hour < 19:
        pass
    if date_hour < 7 or date_hour >= 19:
        entity(204).say(t81.u0)
        return
    if engine.prosperity >= 10 and not recruited(Species.Vegiemon):
        strange_plant_rumor_heard.set()
        entity(204).say(t81.u1)
    if engine.prosperity >= 20:
        entity(204).say(t81.u2)
        return
    if engine.prosperity < 10:
        entity(204).say(t81.u3)
        return
    entity(204).say(t81.u4)

@city_168.on_use(2)
def use2():    # section 82
    if not recruited(Species.Vegiemon):
        return
    raw.set_textbox_origin(600, 0, 1502)
    entity(205).say(t82.u0)

@city_168.on_use(3)
def use3():    # section 83
    if rain_plant_picked or not recruited(Species.Palmon):
        return
    if date_day != 14:
        return
    tamer.say(t83.u0)
    give(Item.RainPlant)
    if engine.item_did_not_fit:
        narrator.say(t83.u1)
        return
    objects[72].show()
    narrator.say(t83.u2)
    rain_plant_picked.set()

@city_168.on_step(1)
def step1():    # section 52
    tamer.walk(171, -327, wait=False)
    if recruited(Species.Angemon) or recruited(Species.Monzaemon) or engine.prosperity >= 50:
        warp(Screen.jijimons_house_205, entry=0)
        return step2()
    warp(Screen.jijimons_house, entry=0)
    return step2()

@city_168.on_step(2)
def step2():    # section 53
    tamer.run(1507, -2574)
    tamer.walk(2061, -1997, wait=False)
    wait(500)
    warp(Screen.birdra_transport, entry=0)

@city_168.on_step(3)
def step3():    # section 54
    if recruited(Species.Drimogemon):
        tamer.walk(401, 3992, wait=False)
        warp(Screen.treasure_hunt, entry=0)

@city_168.on_step(4)
def step4():    # section 55
    if not recruited(Species.Whamon):
        return
    tamer.run(2594, 630, wait=False)
    partner.run(2189, 545, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2128)
    partner.turn(2128)
    wait(250)
    if not whamon_ferry_explained:
        whamon_ferry_explained.set()
        whamon.say(t55.u0)
    whamon.say(t55.u1)
    match choose(a=t55.m0.o0, b=t55.m0.o1, c=t55.m0.o2):
        case "a":
            warp(Screen.factorial_town_152, entry=1)
            warp(Screen.secret_beach_cave_142, entry=2, then=61)
        case "b":
            warp(Screen.secret_beach_cave_142, entry=2, then=61)
        case "c" | _:
            pass
    partner.run(1184, 316, wait=False)
    wait(500)
    tamer.run(1556, 348)
    partner.arrived()
    camera.on(tamer, speed=10)
    camera.arrived()

@city_168.on_step(5)
def step5():    # section 56
    tamer.walk(3583, 3620, wait=False)
    warp(Screen.mt_infinity_166, entry=0)

@city_168.on_step(6)
def step6():    # section 57
    if greymon_challenge_ready and not recruited(Species.Greymon):
        greymon_challenge_ready.clear()
        load(Species.Greymon129)
        spawn(Species.Greymon129, slot=4)
        tamer.face(slot4)
        partner.face(slot4)
        slot4.turn(2048)
        wait(1000)
        camera.on(slot4, speed=20)
        camera.arrived()
        slot4.walk(256, -3385, wait=False)
        slot4.say(t57.u0)
        camera.on(tamer, speed=20)
        camera.arrived()
        tamer.play(15)
        wait(250)
        tamer.say(t57.u1)
        slot4.walk(432, -2236)
        slot4.face(tamer)
        wait(250)
        slot4.say(t57.u2)
        tamer.play(anim.battle_ready)
        wait(250)
        tamer.say(t57.u3)
        slot4.say(t57.u4)
        tamer.play(16)
        wait(1500)
        tamer.say(t57.u5)
        slot4.say(t57.u6)
        partner.run(50, -1950)
        partner.face(slot4)
        wait(250)
        fight(slot4, escape=False)
        tamer.face(slot4)
        slot4.face(tamer)
        partner.face(slot4)
        slot4.say(t57.u7)
        tamer.play(anim.battle_ready)
        wait(250)
        tamer.say(t57.u8)
        slot4.say(t57.u9)
        slot4.walk_away(412, -4500, looks=3)
        slot4.leave()
        glances.set(0)
        sound(8, 12)
        narrator.say(t57.u10)
        greymon_challenge_ready.set()
        recruit(Species.Greymon)
        engine.prosperity.add(2)
        camera.on(tamer, speed=20)
        camera.arrived()
        return
    if mt_infinity_entrance_found and not airdramon_ambush_fought:
        mt_infinity_entrance_found.clear()
        load(Species.Airdramon131)
        spawn(Species.Airdramon131, slot=5)
        tamer.face(slot5)
        partner.face(slot5)
        slot5.face(tamer)
        wait(1000)
        camera.on(slot5, speed=20)
        camera.arrived()
        raw.entity_move_to(slot5, 2084, -211, 30, 0)
        camera.on(tamer, speed=20)
        wait(1000)
        tamer.play(17)
        partner.play(40)
        damage_percent.set(10)
        raw.deal_damage(damage_percent)
        wait(750)
        slot5.run(432, -2236, wait=False)
        camera.to(410, -1474, speed=2)
        camera.arrived()
        slot5.run(432, -2236)
        tamer.face(slot5)
        partner.face(slot5)
        slot5.face(tamer)
        wait(250)
        slot5.say(t57.u11)
        tamer.say(t57.u12)
        slot5.say(t57.u13)
        tamer.say(t57.u14)
        partner.run(50, -1950)
        partner.face(slot5)
        wait(250)
        fight(slot5, escape=False)
        tamer.face(slot5)
        slot5.face(tamer)
        partner.face(slot5)
        slot5.say(t57.u15)
        slot5.play(29)
        wait(1500)
        tamer.play(7)
        wait(250)
        tamer.say(t57.u16)
        raw.entity_walk_to_entity(tamer, 1, slot5)
        raw.entity_walk_to_entity(partner, 1, slot5)
        wait(2000)
        airdramon_ambush_fought.set()
        trigger(355).set()
        mt_infinity_entrance_found.set()
        warp(Screen.jijimons_house_206, entry=1, then=60)
        return
    return

@city_168.on_step(7)
def step7():    # section 58
    if mt_infinity_entrance_found:
        tamer.run(2980, 3318)

@city_168.on_step(8)
def step8():    # section 59
    if mt_infinity_entrance_found:
        tamer.run(1780, 3318)
    return

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 8, 11, 81, 82, 83, 52, 53, 54, 55, 56, 57, 58, 59)
