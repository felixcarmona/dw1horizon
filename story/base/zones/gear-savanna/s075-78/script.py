# The Python view of script 75 of DG.SCN: screen 78 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_78)
leomon = savanna.npc(Species.Leomon166, slot=0)
t5 = text.s075.sec5
t51 = text.s075.sec51
t83 = text.s075.sec83
t85 = text.s075.sec85

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(-1650, 1050))
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(-1650, 2750))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.SweetNut, at=(250, 1450))

@savanna.on_step(0)
def step0():    # section 51
    if leomon_met:
        return
    if recruited(Species.Leomon) or not leomon_rescue_seen:
        return
    tamer.face(leomon)
    partner.face(leomon)
    tamer.arrived()
    partner.arrived()
    leomon_met.set()
    camera.to(-285, 3964, speed=30)
    camera.arrived()
    leomon.say(t51.u0)
    leomon.face(tamer)
    leomon.arrived()
    tamer.play(19)
    wait(750)
    tamer.say(t51.u1)
    tamer.play(anim.idle)
    leomon.say(t51.u2)
    leomon.turn(2560)
    leomon.arrived()
    leomon.play(24, wait=True)
    tamer.say(t51.u3)
    leomon.say(t51.u4)
    return L6()

@leomon.on_talk
def talk():    # section 5
    say(t5.u0)
    return L6()

@savanna.on_use(3)
def use3():    # section 83
    tamer.turn(2048)
    raw.set_textbox_origin(-829, 0, 4099)
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

@savanna.on_use(5)
def use5():    # section 85
    tamer.turn(2560)
    raw.set_textbox_origin(766, 0, 106)
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

def L6():    # shared code (the disc's label L6)
    if has(Item.Leomonstone):
        take(Item.Leomonstone)
    else:
        tamer.say(t51.u5)
        leomon.say(t51.u6)
        leomon.say(t51.u7)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    tamer.play(19)
    wait(750)
    tamer.say(t51.u8)
    tamer.play(anim.idle)
    leomon.face(tamer)
    leomon.arrived()
    leomon.say(t51.u9)
    camera.on(leomon, speed=20)
    camera.arrived()
    raw.entity_walk_to_entity_with_camera(leomon, 1, tamer)
    leomon.arrived()
    leomon.face(tamer)
    tamer.face(leomon)
    leomon.arrived()
    tamer.arrived()
    leomon.play(25)
    wait(1500)
    leomon.say(t51.u10)
    leomon.say(t51.u11)
    leomon.play(24, wait=True)
    leomon.say(t51.u12)
    tamer.say(t51.u13)
    leomon.play(22, wait=True)
    leomon.say(t51.u14)
    leomon.walk_away(-374, -1119, looks=3)
    leomon.send_to_city(line=t51.u15, species=Species.Leomon, sound=(8, 17), prosperity=2)

# the section table, in the order of the original header
sections(254, 51, 5, 83, 85)
