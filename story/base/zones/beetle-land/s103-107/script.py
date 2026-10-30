# The Python view of script 103 of DG.SCN: screen 107 Beetle Land.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

land = screen(Screen.beetle_land_107)
kabuterimon0 = land.npc(Species.Kabuterimon141, slot=0)
kabuterimon1 = land.npc(Species.Kabuterimon141, slot=1)
kabuterimon2 = land.npc(Species.Kabuterimon141, slot=2)
t5 = text.s103.sec5
t6 = text.s103.sec6
t7 = text.s103.sec7
t81 = text.s103.sec81
t83 = text.s103.sec83

@land.on_enter
def enter():    # section 254
    pass

@kabuterimon0.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.say(t5.u1)
    say(t5.u2)
    if not recruited(Species.Greymon):
        tamer.say(t5.u3)
        say(t5.u4)
        return
    dws(r"""
        choice(open) {
            text("s103.sec5.m0.o0") => {
                say(kabuterimon0, text("s103.sec5.u5"));
                return;
            }
            text("s103.sec5.m0.o1") => {
                say(kabuterimon0, text("s103.sec5.u6"));
                walk_away(kabuterimon0, -1342, -2147, looks: 3);
                join_city(kabuterimon0, species("Kabuterimon"), 8, 17, text("s103.sec5.u7"), prosperity: 2);
                return;
            }
        }
    """)

@kabuterimon1.on_talk
def talk():    # section 6
    say(t6.u0)
    if insect_contest_horn_helmet_won:
        say(t6.u1)
        return
    say(t6.u2)

@kabuterimon2.on_talk
def talk():    # section 7
    if knows(Tech.Bug):
        say(t7.u0)
        return
    say(t7.u1)
    match choose(a=t7.m0.o0, b=t7.m0.o1):
        case "a":
            say(t7.u2)
            if partner.defense < 500:
                say(t7.u3)
                return
            if partner.speed < 500:
                say(t7.u4)
                return
            if partner.max_hp < 500:
                say(t7.u5)
                return
            raw.learn_move(Tech.Bug)
            say(t7.u6)
            narrator.say(t7.u7)
            arrived()
            camera.on(tamer, speed=10)
            camera.arrived()
            return
        case "b":
            return
        case _:
            return

@land.on_use(1)
def use1():    # section 81
    tamer.turn(2128)
    raw.set_textbox_origin(-541, 0, 1823)
    call(Routine.load_training_library)
    entity(200).say(t81.u0)
    match entity(200).choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "b":
            while True:
                raw.show_textbox(t81.u1)
                dws(r"""
                    choice(keep) {
                        text("s103.sec81.m2.o0") => {}
                        text("s103.sec81.m2.o1") => {
                            break;
                        }
                        text("s103.sec81.m2.o2") or cancel => {
                            return;
                        }
                    }
                """)
        case "c" | _:
            return
    dws(r"""
        choice(narrator) {
            text("s103.sec81.m1.o0") => {
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
            text("s103.sec81.m1.o1") => {
                set_textbox_mode(1, 0);
                say(narrator, text("s103.sec81.u2"));
                engine.arg = 0;
                training_slot_game = 1;
                call_digimon_routine(214);
                call_routine(routine("training"));
                set_textbox_mode(0, 0);
            }
            text("s103.sec81.m1.o2") or cancel => {}
        }
    """)

@land.on_use(3)
def use3():    # section 83
    tamer.turn(1968)
    raw.set_textbox_origin(-1330, 0, 1434)
    call(Routine.load_training_library)
    entity(200).say(t83.u0)
    match entity(200).choose(a=t83.m0.o0, b=t83.m0.o1, c=t83.m0.o2):
        case "b":
            while True:
                entity(200).say(t83.u1)
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
            narrator.say(t83.u2)
            engine.arg.set(1)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

# the section table, in the order of the original header
sections(254, 5, 6, 7, 81, 83)
