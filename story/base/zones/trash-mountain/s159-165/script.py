# The Python view of script 159 of DG.SCN: screen 165 Trash Mountain.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mountain = screen(Screen.trash_mountain_165)
kingsukamon = mountain.npc(Species.KingSukamon, slot=0)
sukamon1 = mountain.npc(Species.Sukamon, slot=1)
sukamon2 = mountain.npc(Species.Sukamon, slot=2)
sukamon3 = mountain.npc(Species.Sukamon, slot=3)
t51 = text.s159.sec51
t6 = text.s159.sec6
t7 = text.s159.sec7
t8 = text.s159.sec8
t81 = text.s159.sec81
t82 = text.s159.sec82

@mountain.on_enter
def enter():    # section 254
    if not old_fishrod_picked_up:
        objects[10].hide()
    else:
        objects[10].show()
    if not dust_kingdom_explained:
        return sukamon1.talk()

@kingsukamon.on_talk
def talk():    # section 5
    return use1()

@mountain.on_use(1)
def use1():    # section 81
    camera.to(-1143, 1558, speed=10)
    tamer.face(kingsukamon)
    partner.face(kingsukamon)
    kingsukamon.face(tamer)
    wait(250)
    raw.store_digimon_type(partner_type)
    if kingsukamon_reverted_partner and partner_type == 39:
        sound(8, 20)
        kingsukamon.say(t81.u0)
        tamer.play(16)
        wait(750)
        tamer.say(t81.u1)
        tamer.play(anim.idle)
        kingsukamon.say(t81.u2)
    else:
        if kingsukamon_reverted_partner:
            sound(8, 20)
            kingsukamon.say(t81.u3)
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        if partner_type == 39:
            kingsukamon.say(t81.u4)
            engine.no_cancel.set()
            dws(r"""
                choice(open) {
                    text("s159.sec81.m0.o0") => {
                        engine.no_cancel = false;
                        sound(8, 20);
                        say(kingsukamon, text("s159.sec81.u5"));
                        say(tamer, text("s159.sec81.u6"));
                        say(kingsukamon, text("s159.sec81.u7"));
                        camera_on(tamer, speed: 10);
                        await camera;
                        return;
                    }
                    text("s159.sec81.m0.o1") => {
                        engine.no_cancel = false;
                        say(kingsukamon, text("s159.sec81.u8"));
                        animate(tamer, 16);
                        wait(15);
                        say(tamer, text("s159.sec81.u9"));
                        animate(tamer, anim.idle);
                        say(kingsukamon, text("s159.sec81.u10"));
                        say(tamer, text("s159.sec81.u11"));
                        say(kingsukamon, text("s159.sec81.u12"));
                        say(tamer, text("s159.sec81.u13"));
                        sound(8, 20);
                        say(kingsukamon, text("s159.sec81.u14"));
                        if (damage_percent == 39) {
                            store_digimon_type(damage_percent);
                            copy_pstat(sukamon_backup_digimon, engine.arg);
                        }
                        fadeout_hud(0);
                        animate(kingsukamon, 30);
                        sound(8, 19);
                        wait(3s);
                        call_digimon_routine(routine("revert_sukamon"));
                        await entity(201);
                        animate(kingsukamon, anim.idle);
                        wait(5);
                        say(tamer, text("s159.sec81.u15"));
                        sound(8, 20);
                        say(kingsukamon, text("s159.sec81.u16"));
                        kingsukamon_reverted_partner = true;
                        camera_on(tamer, speed: 10);
                        await camera;
                        return;
                    }
                    cancel => {}
                }
            """)
        sound(8, 20)
        kingsukamon.say(t81.u17)
        tamer.say(t81.u18)
        kingsukamon.say(t81.u19)
        tamer.say(t81.u20)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if damage_percent == 39:
        raw.store_digimon_type(damage_percent)
        raw.copy_pstat(sukamon_backup_digimon, engine.arg)
    hide_hud()
    kingsukamon.play(30)
    sound(8, 19)
    wait(3000)
    raw.call_digimon_routine(DigimonRoutine.revert_sukamon)
    entity(201).arrived()
    kingsukamon.play(anim.idle)
    wait(250)
    tamer.say(t81.u15)
    sound(8, 20)
    kingsukamon.say(t81.u16)
    kingsukamon_reverted_partner.set()
    camera.on(tamer, speed=10)
    camera.arrived()

@sukamon1.on_talk
def talk():    # section 6
    if dust_kingdom_explained:
        say(t6.u0)
        if has_card(21) >= 1:
            if ask(yes=t6.m0.o0, no=t6.m0.o1):
                if has_card(14) >= 9:
                    say(t6.u29)
                    return
                say(t6.u30)
                raw.take_card(21)
                raw.give_card(14)
        else:
            tamer.say(t6.u1)
    else:
        tamer.play(24)
        wait(750)
        tamer.say(t6.u2)
        tamer.play(anim.idle)
        if not dust_kingdom_explained and partner.species == Species.Sukamon:
            walk(192, -2979)
            say(t6.u3)
            tamer.say(t6.u4)
            say(t6.u5)
            tamer.say(t6.u6)
            say(t6.u7)
            tamer.say(t6.u8)
            say(t6.u9)
            tamer.say(t6.u10)
            walk(189, -1273)
            dust_kingdom_explained.set()
            return
        if not dust_kingdom_explained and raised.drimogemon:
            walk(192, -2979)
            tamer.say(t6.u11)
            say(t6.u12)
            tamer.say(t6.u13)
        else:
            walk(192, -2979)
            say(t6.u14)
            tamer.say(t6.u15)
            say(t6.u16)
            tamer.say(t6.u17)
            say(t6.u18)
            tamer.say(t6.u19)
        say(t6.u20)
        tamer.say(t6.u21)
        say(t6.u22)
        tamer.say(t6.u23)
        say(t6.u24)
        tamer.say(t6.u25)
        say(t6.u26)
        tamer.say(t6.u27)
        say(t6.u28)
        walk(189, -1273)
        dust_kingdom_explained.set()

@sukamon2.on_talk
def talk():    # section 7
    if not recruited(Species.Sukamon):
        recruit(Species.Sukamon)
        engine.prosperity.add(1)
        say(t7.u0)
        return
    say(t7.u1)

@sukamon3.on_talk
def talk():    # section 8
    say(t8.u0)

@mountain.on_step(0)
def step0():    # section 51
    if not have_old_fishrod:
        tamer.say(t51.u0)
        wait(500)
        tamer.play(12)
        wait(500)
        sound(0, 7)
        objects[10].show()
        wait(500)
        have_old_fishrod.set()
        old_fishrod_picked_up.set()

@mountain.on_use(2)
def use2():    # section 82
    tamer.turn(2640)
    raw.set_textbox_origin(1484, 0, -241)
    call(Routine.load_training_library)
    entity(200).say(t82.u0)
    match entity(200).choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "b":
            while True:
                entity(200).say(t82.u1)
                match entity(200).choose(a=t82.m2.o0, b=t82.m2.o1, c=t82.m2.o2):
                    case "b":
                        break
                    case "c" | _:
                        return
        case "c" | _:
            return
    match narrator.choose(a=t82.m1.o0, d=text.qol.training_x5, b=t82.m1.o1, c=t82.m1.o2):
        case "a":
            hide_hud()
            engine.arg.set(4)
            training_slot_game.set(0)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "d":
            hide_hud()
            engine.arg.set(4)
            training_slot_game.set(2)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "b":
            raw.set_textbox_mode(1, 0)
            narrator.say(t82.u2)
            engine.arg.set(4)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

# the section table, in the order of the original header
sections(254, 5, 81, 6, 7, 8, 51, 82)
