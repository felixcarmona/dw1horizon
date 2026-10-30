# The Python view of script 104 of DG.SCN: screen 108 Beetle Land.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

land = screen(Screen.beetle_land_108)
kuwagamon0 = land.npc(Species.Kuwagamon169, slot=0)
kuwagamon1 = land.npc(Species.Kuwagamon169, slot=1)
kuwagamon2 = land.npc(Species.Kuwagamon169, slot=2)
t5 = text.s104.sec5
t6 = text.s104.sec6
t7 = text.s104.sec7
t84 = text.s104.sec84
t85 = text.s104.sec85

@land.on_enter
def enter():    # section 254
    pass

@kuwagamon0.on_talk
def talk():    # section 5
    say(t5.u0)
    match choose(a=t5.m0.o0, b=t5.m0.o1, c=t5.m0.o2):
        case "a":
            say(t5.u1)
            return
        case "b":
            say(t5.u2)
            tamer.play(19)
            wait(750)
            tamer.say(t5.u3)
            tamer.play(anim.idle)
            say(t5.u4)
            walk_away(664, -1963, looks=3)
            send_to_city(line=t5.u5, species=Species.Kuwagamon, sound=(8, 17), prosperity=2, camera=False)
            return
    say(t5.u6)

@kuwagamon1.on_talk
def talk():    # section 6
    if insect_contest_horn_helmet_won:
        say(t6.u0)
        return
    if partner.species in (Species.Kabuterimon, Species.Kunemon, Species.Kuwagamon, Species.HerculesKabuterimon):
        say(t6.u2)
        tamer.say(t6.u3)
        say(t6.u4)
        tamer.say(t6.u5)
        say(t6.u6)
        say(t6.u7)
        return
    say(t6.u1)
    return

@kuwagamon2.on_talk
def talk():    # section 7
    say(t7.u0)
    match choose(a=t7.m0.o0, b=t7.m0.o1):
        case "a":
            raw.store_date(date_year)
            raw.add_minutes_to_date_at(date_year, 60)
            raw.advance_to_date_at(date_year)
            partner.add(hp=300)
            partner.add(mp=300)
            partner.sub(tiredness=5)
            warp(Screen.beetle_land_108, entry=0)
            return
        case "b":
            return
        case _:
            return

@land.on_use(4)
def use4():    # section 84
    tamer.turn(2048)
    raw.set_textbox_origin(-162, 0, 2558)
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

@land.on_use(5)
def use5():    # section 85
    tamer.turn(2048)
    raw.set_textbox_origin(823, 0, 2144)
    call(Routine.load_training_library)
    entity(200).say(t85.u0)
    match entity(200).choose(a=t85.m0.o0, b=t85.m0.o1, c=t85.m0.o2):
        case "b":
            while True:
                entity(200).say(t85.u1)
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
            narrator.say(t85.u2)
            engine.arg.set(2)
            training_slot_game.set(1)
            raw.call_digimon_routine(214)
            call(Routine.training)
            raw.set_textbox_mode(0, 0)
        case "c" | _:
            pass

# the section table, in the order of the original header
sections(254, 5, 6, 7, 84, 85)
