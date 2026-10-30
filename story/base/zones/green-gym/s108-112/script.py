# The Python view of script 108 of DG.SCN: screen 112 Green Gym.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

gym = screen(Screen.green_gym)
koromon = gym.npc(Species.Koromon, slot=0)
kabuterimon = gym.npc(Species.Kabuterimon141, slot=1)
kuwagamon = gym.npc(Species.Kuwagamon169, slot=2)
t5 = text.s108.sec5
t6 = text.s108.sec6
t7 = text.s108.sec7
t81 = text.s108.sec81
t82 = text.s108.sec82
t83 = text.s108.sec83
t84 = text.s108.sec84
t85 = text.s108.sec85
t86 = text.s108.sec86

@gym.on_enter
def enter():    # section 254
    pass

@gym.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    raw.set_textbox_origin(1010, 0, -975)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t81.u0)
    else:
        entity(200).say(t81.u1)
    match entity(200).choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "b":
            while True:
                raw.show_textbox(t81.u2)
                dws(r"""
                    choice(keep) {
                        text("s108.sec81.m2.o0") => {}
                        text("s108.sec81.m2.o1") => {
                            break;
                        }
                        text("s108.sec81.m2.o2") or cancel => {
                            return;
                        }
                    }
                """)
        case "c" | _:
            return
    dws(r"""
        choice(narrator) {
            text("s108.sec81.m1.o0") => {
                fadeout_hud(0);
                engine.arg = 0;
                training_slot_game = 0;
                call_digimon_routine(214);
                call_routine(routine("training"));
            }
            text("qol.training_x5") => {
                fadeout_hud(0);
                engine.arg = 0;
                training_slot_game = 2;
                call_digimon_routine(214);
                call_routine(routine("training"));
            }
            text("s108.sec81.m1.o1") => {
                set_textbox_mode(1, 0);
                say(narrator, text("s108.sec81.u3"));
                engine.arg = 0;
                training_slot_game = 1;
                call_digimon_routine(214);
                call_routine(routine("training"));
                set_textbox_mode(0, 0);
            }
            text("s108.sec81.m1.o2") or cancel => {}
        }
    """)

@gym.on_use(2)
def use2():    # section 82
    tamer.turn(2048)
    raw.set_textbox_origin(1432, 0, 1276)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t82.u0)
    else:
        entity(200).say(t82.u1)
    match entity(200).choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "b":
            while True:
                entity(200).say(t82.u2)
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
            narrator.say(t82.u3)
            engine.arg.set(4)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

@gym.on_use(3)
def use3():    # section 83
    tamer.turn(2048)
    raw.set_textbox_origin(-506, 0, -1937)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t83.u0)
    else:
        entity(200).say(t83.u1)
    match entity(200).choose(a=t83.m0.o0, b=t83.m0.o1, c=t83.m0.o2):
        case "b":
            while True:
                entity(200).say(t83.u2)
                match entity(200).choose(a=t83.m2.o0, b=t83.m2.o1, c=t83.m2.o2):
                    case "b":
                        break
                    case "c" | _:
                        return
        case "c" | _:
            return
    match narrator.choose(a=t83.m1.o0, d=text.qol.training_x5, b=t83.m1.o1, c=t83.m1.o2):
        case "a":
            hide_hud()
            engine.arg.set(1)
            training_slot_game.set(0)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "d":
            hide_hud()
            engine.arg.set(1)
            training_slot_game.set(2)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "b":
            raw.set_textbox_mode(1, 0)
            narrator.say(t83.u3)
            engine.arg.set(1)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

@gym.on_use(4)
def use4():    # section 84
    tamer.turn(2048)
    raw.set_textbox_origin(-789, 0, -875)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t84.u0)
    else:
        entity(200).say(t84.u1)
    match entity(200).choose(a=t84.m0.o0, b=t84.m0.o1, c=t84.m0.o2):
        case "b":
            while True:
                entity(200).say(t84.u2)
                match entity(200).choose(a=t84.m2.o0, b=t84.m2.o1, c=t84.m2.o2):
                    case "b":
                        break
                    case "c" | _:
                        return
        case "c" | _:
            return
    match narrator.choose(a=t84.m1.o0, d=text.qol.training_x5, b=t84.m1.o1, c=t84.m1.o2):
        case "a":
            hide_hud()
            engine.arg.set(3)
            training_slot_game.set(0)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "d":
            hide_hud()
            engine.arg.set(3)
            training_slot_game.set(2)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "b":
            raw.set_textbox_mode(1, 0)
            narrator.say(t84.u3)
            engine.arg.set(3)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

@gym.on_use(5)
def use5():    # section 85
    tamer.turn(2048)
    raw.set_textbox_origin(12, 0, 445)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t85.u0)
    else:
        entity(200).say(t85.u1)
    match entity(200).choose(a=t85.m0.o0, b=t85.m0.o1, c=t85.m0.o2):
        case "b":
            while True:
                entity(200).say(t85.u2)
                match entity(200).choose(a=t85.m2.o0, b=t85.m2.o1, c=t85.m2.o2):
                    case "b":
                        break
                    case "c" | _:
                        return
        case "c" | _:
            return
    match narrator.choose(a=t85.m1.o0, d=text.qol.training_x5, b=t85.m1.o1, c=t85.m1.o2):
        case "a":
            hide_hud()
            engine.arg.set(2)
            training_slot_game.set(0)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "d":
            hide_hud()
            engine.arg.set(2)
            training_slot_game.set(2)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "b":
            raw.set_textbox_mode(1, 0)
            narrator.say(t85.u3)
            engine.arg.set(2)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

@gym.on_use(6)
def use6():    # section 86
    tamer.turn(1536)
    raw.set_textbox_origin(-1779, 0, 2084)
    call(Routine.load_training_library)
    if recruited(Species.Kabuterimon):
        entity(200).say(t86.u0)
    else:
        entity(200).say(t86.u1)
    match entity(200).choose(a=t86.m0.o0, b=t86.m0.o1, c=t86.m0.o2):
        case "b":
            while True:
                entity(200).say(t86.u2)
                match entity(200).choose(a=t86.m2.o0, b=t86.m2.o1, c=t86.m2.o2):
                    case "b":
                        break
                    case "c" | _:
                        return
        case "c" | _:
            return
    match narrator.choose(a=t86.m1.o0, d=text.qol.training_x5, b=t86.m1.o1, c=t86.m1.o2):
        case "a":
            hide_hud()
            engine.arg.set(5)
            training_slot_game.set(0)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "d":
            hide_hud()
            engine.arg.set(5)
            training_slot_game.set(2)
            raw.call_digimon_routine(214)
            call(Routine.training)
        case "b":
            raw.set_textbox_mode(1, 0)
            narrator.say(t86.u3)
            engine.arg.set(5)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

@koromon.on_talk
def talk():    # section 5
    if engine.prosperity >= 40:
        say(t5.u0)
        return
    if engine.prosperity >= 20:
        say(t5.u1)
        return
    if engine.prosperity >= 5:
        say(t5.u2)
        return
    say(t5.u3)
    match choose(a=t5.m0.o0, b=t5.m0.o1, c=t5.m0.o2):
        case "a":
            say(t5.u4)
            return
        case "b":
            say(t5.u5)
            say(t5.u6)
            return
    say(t5.u7)

@gym.on_step(0)
def step0():    # section 51
    tamer.walk(2200, -3000, wait=False)
    if not recruited(Species.Agumon):
        warp(Screen.file_city_204, entry=1)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=1)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=1)
            warp(Screen.file_city_168, entry=1)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=1)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=1)
        warp(Screen.file_city_171, entry=1)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=1)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=1)
        warp(Screen.file_city_174, entry=1)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=1)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=1)
    warp(Screen.file_city_177, entry=1)

@kabuterimon.on_talk
def talk():    # section 6
    say(t6.u0)

@kuwagamon.on_talk
def talk():    # section 7
    say(t7.u0)
    return

# the section table, in the order of the original header
sections(254, 81, 82, 83, 84, 85, 86, 5, 51, 6, 7)
