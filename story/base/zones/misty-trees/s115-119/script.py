# The Python view of script 115 of DG.SCN: screen 119 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_119)
cherrymon = trees.npc(Species.Cherrymon, slot=0)
t5 = text.s115.sec5
t51 = text.s115.sec51

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 18:
        spawn_item(Item.Digimushrm, at=(650, 1550))
    roll = random.roll(99)
    if roll <= 12:
        spawn_item(Item.Digimushrm, at=(650, -3050))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Digipine, at=(-1450, -1450))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.CalmBerry, at=(1750, 1750))
    if cherrymon_met:
        raw.entity_move_to(cherrymon, -2017, 1378, 3, 0)
        entity(20).arrived()
        cherrymon.turn(0)
        wait(250)

@trees.on_step(0)
def step0():    # section 51
    if not cherrymon_met:
        cherrymon_met.set()
    else:
        return
    tamer.run(-1606, 166, camera=True, wait=False)
    partner.run(-1407, 465)
    tamer.arrived()
    tamer.face(cherrymon)
    cherrymon.face(tamer)
    partner.face(cherrymon)
    sound(8, 18)
    cherrymon.say(t51.u0)
    tamer.play(20)
    wait(750)
    if recruited(Species.Otamamon):
        tamer.say(t51.u1)
    else:
        tamer.say(t51.u2)
    tamer.play(anim.idle)
    cherrymon.say(t51.u3)
    if recruited(Species.Otamamon):
        tamer.say(t51.u4)
    else:
        tamer.say(t51.u5)
    sound(8, 18)
    cherrymon.say(t51.u6)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u7)
    tamer.play(anim.idle)
    cherrymon.say(t51.u8)
    tamer.say(t51.u9)
    cherrymon.say(t51.u10)
    return L12()

@cherrymon.on_talk(scene=True)
def talk():    # section 5
    say(t5.u0)
    match choose(a=t5.m0.o0, b=t5.m0.o1, c=t5.m0.o2):
        case "a":
            say(t5.u1)
            return L12()
        case "b":
            say(t5.u2)
            call(Routine.load_training_library)
            raw.set_textbox_origin(-2017, 0, 1378)
            narrator.say(t5.u3)
            match narrator.choose(a=t5.m1.o0, b=t5.m1.o1, c=t5.m1.o2):
                case "b":
                    while True:
                        narrator.say(t5.u4)
                        match narrator.choose(a=t5.m3.o0, b=t5.m3.o1, c=t5.m3.o2):
                            case "b":
                                break
                            case "c" | _:
                                return
                case "c" | _:
                    return
            match narrator.choose(a=t5.m2.o0, d=text.qol.training_x5, b=t5.m2.o1, c=t5.m2.o2):
                case "a":
                    hide_hud()
                    engine.arg.set(5)
                    training_slot_game.set(0)
                    raw.call_digimon_routine(214)
                    call(Routine.training)
                    return
                case "d":
                    hide_hud()
                    engine.arg.set(5)
                    training_slot_game.set(2)
                    raw.call_digimon_routine(214)
                    call(Routine.training)
                    return
                case "b":
                    raw.set_textbox_mode(1, 0)
                    narrator.say(t5.u5)
                    engine.arg.set(5)
                    training_slot_game.set(1)
                    raw.call_digimon_routine(214)
                    call(Routine.training)
                    raw.set_textbox_mode(0, 0)
                    return
                case "c" | _:
                    return
        case "c" | _:
            pass
    say(t5.u6)

def L12():    # shared code (the disc's label L12)
    sound(8, 18)
    cherrymon.say(t51.u11)
    sound(8, 18)
    raw.show_textbox(t51.u12)
    sound(8, 18)
    raw.show_textbox(t51.u13)
    if not misty_trees_fog_lifted:
        misty_trees_fog_lifted.set()
        sound(8, 18)
        cherrymon.say(t51.u14)
        call(Routine.remove_fog)
    else:
        return
    cherrymon.say(t51.u15)
    sound(8, 18)
    raw.show_textbox(t51.u16)
    cherrymon.play(29)
    wait(3000)

# the section table, in the order of the original header
sections(254, 51, 5)
