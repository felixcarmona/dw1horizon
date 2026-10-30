# The Python view of script 163 of DG.SCN: screen 180 File City, screen 181 File City, screen 182 File City, screen 183 File City, screen 184 File City, screen 185 File City, screen 186 File City, screen 187 File City, screen 188 File City, screen 189 File City, screen 190 File City, screen 191 File City, screen 192 File City, screen 193 File City, screen 194 File City, screen 195 File City, screen 196 File City, screen 197 File City, screen 198 File City, screen 199 File City, screen 200 File City, screen 201 File City, screen 202 File City, screen 203 File City.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

city_180 = screen(Screen.file_city_180)
city_181 = screen(Screen.file_city_181)
city_182 = screen(Screen.file_city_182)
city_183 = screen(Screen.file_city_183)
city_184 = screen(Screen.file_city_184)
city_185 = screen(Screen.file_city_185)
city_186 = screen(Screen.file_city_186)
city_187 = screen(Screen.file_city_187)
city_188 = screen(Screen.file_city_188)
city_189 = screen(Screen.file_city_189)
city_190 = screen(Screen.file_city_190)
city_191 = screen(Screen.file_city_191)
city_192 = screen(Screen.file_city_192)
city_193 = screen(Screen.file_city_193)
city_194 = screen(Screen.file_city_194)
city_195 = screen(Screen.file_city_195)
city_196 = screen(Screen.file_city_196)
city_197 = screen(Screen.file_city_197)
city_198 = screen(Screen.file_city_198)
city_199 = screen(Screen.file_city_199)
city_200 = screen(Screen.file_city_200)
city_201 = screen(Screen.file_city_201)
city_202 = screen(Screen.file_city_202)
city_203 = screen(Screen.file_city_203)
bakemon = city_180.npc(Species.Bakemon157, slot=0)
shellmon = city_180.npc(Species.Shellmon155, slot=1)
betamon = city_180.npc(Species.Betamon128, slot=2)
kunemon = city_180.npc(Species.Kunemon152, slot=3)
tsunomon = city_180.npc(Species.Tsunomon, slot=4)
elecmon = city_180.npc(Species.Elecmon140, slot=5)
megadramon = city_180.npc(Species.Megadramon172, slot=6)
ogremon = city_180.npc(Species.Ogremon154, slot=7)
t10 = text.s163.sec10
t11 = text.s163.sec11
t12 = text.s163.sec12
t5 = text.s163.sec5
t6 = text.s163.sec6
t7 = text.s163.sec7
t8 = text.s163.sec8
t81 = text.s163.sec81
t9 = text.s163.sec9

@city_180.on_enter
def enter():    # section 254
    raw.store_date(date_year)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Betamon):
            raw.set_rect_impassable(0, 47, 48, 7, 8)
            objects[0].hide()
            objects[1].hide()
            objects[2].hide()
            objects[3].hide()
            objects[4].hide()
            objects[5].hide()
            objects[6].hide()
            objects[65].hide()
            objects[66].hide()
    if engine.game_beaten:
        raw.set_rect_impassable(0, 47, 48, 7, 8)
        objects[0].hide()
        objects[1].hide()
        objects[2].hide()
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
        objects[65].hide()
        objects[66].show()
        objects[67].hide()
    if recruited(Species.Shellmon):
        raw.set_rect_impassable(0, 71, 50, 1, 9)
        objects[13].hide()
        objects[14].hide()
        objects[15].hide()
        objects[16].hide()
        objects[17].hide()
        objects[18].hide()
        objects[19].hide()
        objects[20].hide()
        objects[21].hide()
        objects[22].hide()
        objects[23].hide()
    if date_hour < 7 or date_hour >= 19:
        if recruited(Species.Elecmon) and recruited(Species.Shellmon):
            objects[68].hide()
            objects[69].hide()
            objects[70].hide()
            objects[71].hide()
            objects[72].hide()
            objects[73].hide()
    if recruited(Species.Kunemon):
        objects[24].show()
        objects[25].show()
    else:
        raw.set_rect_impassable(0, 79, 38, 2, 4)
        raw.set_rect_impassable(0, 80, 42, 2, 8)
    if not recruited(Species.Centarumon):
        pass
    elif date_hour < 7 or date_hour >= 19:
        if recruited(Species.Elecmon):
            objects[49].hide()
            objects[50].hide()
    if recruited(Species.Elecmon):
        objects[53].hide()
        objects[54].hide()
        objects[55].hide()
        objects[56].hide()
    if date_hour < 7 or date_hour >= 19:
        if recruited(Species.Elecmon):
            objects[57].hide()
            objects[58].hide()
            objects[59].hide()
            objects[60].hide()
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if date_hour < 7 or date_hour >= 19:
            if recruited(Species.Elecmon):
                objects[61].hide()
                objects[62].hide()
                objects[63].hide()
                objects[64].hide()
    if not recruited(Species.Coelamon) and city_layout == 2:
        objects[108].show()
    if not recruited(Species.Coelamon) and city_layout == 3:
        objects[109].show()
    if not recruited(Species.Coelamon) and city_layout == 4:
        objects[111].show()
    if not recruited(Species.Coelamon) and city_layout == 5:
        objects[143].show()
    if not recruited(Species.Coelamon) and city_layout == 6:
        objects[139].show()
    if not recruited(Species.Coelamon) and city_layout == 7:
        objects[108].show()
    if not recruited(Species.Coelamon) and city_layout == 8:
        objects[140].show()
    if not recruited(Species.Coelamon) and city_layout == 9:
        objects[138].show()
    curling_opponent.set(255)
    if not recruited(Species.Betamon):
        return
    if not recruited(Species.Patamon) and not recruited(Species.Biyomon) and not recruited(Species.Unimon) and not recruited(Species.Monochromon):
        raw.entity_move_to(betamon, -1232, 2903, 10, 0)
        wait(750)
        betamon.turn(3664)
        wait(250)

@bakemon.on_talk
def talk():    # section 5
    city_resident_met.bakemon.set()
    say(t5.u0)
    tamer.say(t5.u1)
    if partner.species == Species.Bakemon:
        tamer.face(partner)
        wait(250)
        partner.play(11)
        wait(500)
        tamer.face(partner)
        wait(250)
        tamer.say(t5.u2)

@shellmon.on_talk
def talk():    # section 6
    if not shellmon_newspaper_started:
        shellmon_newspaper_started.set()
        say(t6.u0)
        say(t6.u1)
        say(t6.u2)
        return
    say(t6.u3)

@betamon.on_talk
def talk():    # section 7
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        say(t7.u0)
        return
    if recruited(Species.Betamon) and not betamon_shop_met.opened and not recruited(Species.Coelamon):
        betamon_shop_met.opened.set()
        say(t7.u1)
        return
    if recruited(Species.Betamon) and recruited(Species.Coelamon) and not betamon_shop_met.coelamon_joined:
        betamon_shop_met.coelamon_joined.set()
        say(t7.u2)
        narrator.say(t7.u3)
        return
    if recruited(Species.Betamon) and recruited(Species.Coelamon):
        shop(Item.SmRecovery, Item.MedRecovery, Item.MPFloppy, Item.Various, Item.AutoPilot, Item.Meat)
        return
    shop(Item.SmRecovery, Item.MPFloppy, Item.Meat)

@kunemon.on_talk
def talk():    # section 8
    if not city_resident_met.kunemon:
        city_resident_met.kunemon.set()
        say(t8.u0)
        return
    if engine.prosperity <= 30:
        say(t8.u1)
        say(t8.u2)
        return
    match pstat(37):
        case 0:
            say(t8.u3)
            pstat(37).add(1)
        case 1:
            say(t8.u4)
            pstat(37).add(1)
        case 2:
            say(t8.u5)
        case 3:
            say(t8.u6)
        case 4:
            say(t8.u7)
        case 5:
            say(t8.u8)
        case 6:
            say(t8.u9)
        case 7 | _:
            say(t8.u10)

@tsunomon.on_talk
def talk():    # section 9
    if engine.prosperity >= 20 and eastern_bridge_seen:
        say(t9.u0)
        dws(r"""
            choice(open) {
                text("s163.sec9.m0.o0") => {
                    if (engine.prosperity >= 25) {
                        say(tsunomon, text("s163.sec9.u4"));
                        return;
                    }
                    say(tsunomon, text("s163.sec9.u5"));
                    return;
                }
                text("s163.sec9.m0.o1") => {
                    say(tsunomon, text("s163.sec9.u6"));
                    return;
                }
                cancel => {}
            }
        """)
    if eastern_bridge_seen:
        say(t9.u1)
        return
    if engine.prosperity >= 2 and not eastern_bridge_seen:
        say(t9.u2)
        return
    say(t9.u3)

@elecmon.on_talk
def talk():    # section 10
    if not city_resident_met.elecmon:
        city_resident_met.elecmon.set()
        say(t10.u0)
        say(t10.u1)
        return
    say(t10.u2)
    say(t10.u3)

@megadramon.on_talk
def talk():    # section 11
    say(t11.u0)

@ogremon.on_talk
def talk():    # section 12
    say(t12.u0)

@city_180.on_use(1)
def use1():    # section 81
    tamer.turn(1024)
    sound(0, 0)
    wait(250)
    raw.set_textbox_origin(-628, 0, 2226)
    if recruited(Species.Coelamon) and not betamon_shop_met.opened and not recruited(Species.Betamon):
        betamon_shop_met.opened.set()
        entity(203).say(t81.u0)
        return
    if recruited(Species.Betamon) and not betamon_shop_met.opened and not recruited(Species.Coelamon):
        betamon_shop_met.opened.set()
        entity(202).say(t81.u1)
        sound(0, 1)
        return
    if recruited(Species.Betamon) and recruited(Species.Coelamon) and not betamon_shop_met.coelamon_joined:
        betamon_shop_met.coelamon_joined.set()
        entity(202).say(t81.u2)
        narrator.say(t81.u3)
        sound(0, 1)
        return
    if recruited(Species.Betamon) and recruited(Species.Coelamon):
        shop_stock.sm_recovery.set()
        shop_stock.med_recovery.set()
        shop_stock.mp_floppy.set()
        shop_stock.various.set()
        shop_stock.auto_pilot.set()
        shop_stock.meat.set()
        engine.picker_mode.clear()
        call(Routine.shop, arg=255)
        shop_stock.sm_recovery.clear()
        shop_stock.med_recovery.clear()
        shop_stock.mp_floppy.clear()
        shop_stock.various.clear()
        shop_stock.auto_pilot.clear()
        shop_stock.meat.clear()
        return
    shop_stock.sm_recovery.set()
    shop_stock.mp_floppy.set()
    shop_stock.meat.set()
    engine.picker_mode.clear()
    if recruited(Species.Coelamon):
        engine.arg.set(255)
    else:
        engine.arg.set(7)
    call(Routine.shop)
    shop_stock.sm_recovery.clear()
    shop_stock.mp_floppy.clear()
    shop_stock.meat.clear()

@city_180.on_use(2)
def use2():    # section 82
    if recruited(Species.Shellmon):
        jump_to_script(208, 82)

@city_180.on_step(0)
def step0():    # section 51
    tamer.walk(-3000, 492, wait=False)
    warp(Screen.native_forest_109, entry=2)

@city_180.on_step(2)
def step2():    # section 53
    if not recruited(Species.Kunemon):
        return
    if eastern_bridge_seen:
        tamer.walk(3500, 952, wait=False)
        warp(Screen.digimon_bridge_9, entry=0)
    else:
        tamer.walk(3500, 952, wait=False)
        warp(Screen.digimon_bridge_10, entry=0)

@city_180.on_step(3)
def step3():    # section 54
    tamer.walk(-1464, 1954, wait=False)
    warp(Screen.item_shop, entry=0)

@city_180.on_step(4)
def step4():    # section 55
    tamer.walk(1853, 1853, wait=False)
    if recruited(Species.Giromon):
        warp(Screen.restaurant_215, entry=0)
    warp(Screen.restaurant_214, entry=0)

@city_180.on_step(5)
def step5():    # section 56
    tamer.walk(-1291, -1863, wait=False)
    warp(Screen.centar_clinic, entry=0)

@city_180.on_step(6)
def step6():    # section 57
    tamer.walk(1481, -3326, wait=False)
    if engine.game_beaten:
        warp(Screen.arena_lobby_223, entry=1)
        return
    warp(Screen.arena_lobby_208, entry=1)

@city_180.on_step(1)
def step1():    # section 52
    tamer.walk(0, 5000, wait=False)
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
sections(254, 5, 6, 7, 8, 9, 10, 11, 12, 81, 82, 51, 53, 54, 55, 56, 57, 52)
