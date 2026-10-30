# The Python view of script 95 of DG.SCN: screen 99 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sanctuary = screen(Screen.ice_sanctuary_99)
t81 = text.s095.sec81
t84 = text.s095.sec84

@sanctuary.on_enter
def enter():    # section 254
    pass

@sanctuary.on_step(0)
def step0():    # section 51
    tamer.walk(969, -3260, wait=False)
    warp(Screen.ice_sanctuary_98, entry=1)

@sanctuary.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    raw.set_textbox_origin(-11, 0, 1049)
    call(Routine.load_training_library)
    entity(200).say(t81.u0)
    match entity(200).choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "b":
            while True:
                raw.show_textbox(t81.u1)
                dws(r"""
                    choice(keep) {
                        text("s095.sec81.m2.o0") => {}
                        text("s095.sec81.m2.o1") => {
                            break;
                        }
                        text("s095.sec81.m2.o2") or cancel => {
                            return;
                        }
                    }
                """)
        case "c" | _:
            return
    dws(r"""
        choice(narrator) {
            text("s095.sec81.m1.o0") => {
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
            text("s095.sec81.m1.o1") => {
                set_textbox_mode(1, 0);
                say(narrator, text("s095.sec81.u2"));
                engine.arg = 0;
                training_slot_game = 1;
                call_digimon_routine(214);
                call_routine(routine("training"));
                set_textbox_mode(0, 0);
            }
            text("s095.sec81.m1.o2") or cancel => {}
        }
    """)

@sanctuary.on_use(4)
def use4():    # section 84
    tamer.turn(2048)
    raw.set_textbox_origin(1574, 0, 116)
    call(Routine.load_training_library)
    entity(200).say(t84.u0)
    match entity(200).choose(a=t84.m0.o0, b=t84.m0.o1, c=t84.m0.o2):
        case "b":
            while True:
                entity(200).say(t84.u1)
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
            narrator.say(t84.u2)
            engine.arg.set(3)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

# the section table, in the order of the original header
sections(254, 51, 81, 84)
