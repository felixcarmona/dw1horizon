# The Python view of script 140 of DG.SCN: screen 146 Robot House.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

house = screen(Screen.robot_house)
tinmon0 = house.npc(Species.Tinmon, slot=0)
slot1 = house.npc(None, slot=1)    # the .MAP has Hagurumon here; the script spawns what stands here
tinmon2 = house.npc(Species.Tinmon, slot=2)
tinmon3 = house.npc(Species.Tinmon, slot=3)
t5 = text.s140.sec5
t6 = text.s140.sec6
t7 = text.s140.sec7
t8 = text.s140.sec8

@house.on_enter
def enter():    # section 254
    call(Routine.spawn_gearbox)
    if toy_tale_heard:
        engine.music_mode.set(4)
        music(22)
        call(Routine.toytown_select_box, arg=0)
        load(Species.Hagurumon)
        spawn(Species.Hagurumon, slot=1)
        raw.entity_move_to(slot1, -100, 1758, 1, 0)
        slot1.arrived()
        slot1.play(29)
        slot1.turn(0)

@house.on_step(0)
def step0():    # section 51
    if not toy_tale_heard and recruited(Species.WaruMonzaemon):
        tamer.walk(-52, 650, camera=True)
        tamer.turn(2065)
        wait(250)
        return tinmon0.talk()

@tinmon0.on_talk
def talk():    # section 5
    if recruited(Species.WaruMonzaemon) and not toy_tale_heard and has(Item.Gear):
        take(Item.Gear)
        load(Species.Hagurumon)
        spawn(Species.Hagurumon, slot=1)
        slot1.play(29)
        tamer.play(15)
        wait(1000)
        sound(8, 4)
        tamer.play(16)
        wait(750)
        tamer.say(t5.u0)
        tamer.play(anim.idle)
        tamer.face(slot1)
        sound(8, 9)
        wait(500)
        say(t5.u1)
        tamer.say(t5.u2)
        sound(8, 8)
        camera.to(-80, 1048, speed=18)
        raw.entity_move_to(slot1, -100, 1758, 20, 0)
        slot1.arrived()
        slot1.turn(0)
        wait(250)
        slot1.play(30)
        tamer.play(16)
        wait(750)
        tamer.say(t5.u3)
        tamer.play(anim.idle)
        call(Routine.toytown_select_box, arg=1)
    else:
        if recruited(Species.WaruMonzaemon) and toy_tale_heard and not has(Item.Gear) and not toy_tale_heard:
            say(t5.u13)
            return
        if toy_mansion_seal_lifted and not recruited(Species.WaruMonzaemon):
            say(t5.u14)
            return
        if partner.species == Species.Monzaemon and not toy_mansion_seal_lifted:
            toy_mansion_seal_lifted.set()
            say(t5.u17)
            tamer.say(t5.u18)
            say(t5.u19)
            tamer.say(t5.u20)
            say(t5.u21)
            tamer.play(25)
            wait(750)
            tamer.say(t5.u22)
            tamer.play(anim.idle)
            say(t5.u23)
            say(t5.u24)
            tamer.say(t5.u25)
            say(t5.u26)
            tamer.say(t5.u27)
            return
        say(t5.u15)
        return
    camera.to(-80, 1048, speed=18)
    engine.music_mode.set(4)
    music(22)
    tinmon2.walk(248, -447, wait=False)
    tinmon3.walk(-747, 459, wait=False)
    tinmon2.arrived()
    tinmon3.arrived()
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u4)
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u5)
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u6)
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u7)
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u8)
    play(29)
    tinmon2.play(29)
    tinmon3.play(29)
    wait(500)
    sound(8, 9)
    narrator.say(t5.u9)
    play(anim.idle)
    tinmon2.play(anim.idle)
    tinmon3.play(anim.idle)
    wait(500)
    if toy_tale_heard:
        return
    toy_tale_heard.set()
    tamer.say(t5.u10)
    sound(8, 8)
    say(t5.u11)
    recruit(Species.Monzaemon)
    engine.prosperity.add(3)
    sound(8, 10)
    narrator.say(t5.u12)
    camera.on(tamer, speed=15)
    camera.arrived()
    call(Routine.toytown_select_box, arg=0)
    return

@slot1.on_talk
def talk():    # section 6
    sound(8, 8)
    say(t6.u0)

@tinmon2.on_talk
def talk():    # section 7
    if toy_tale_heard:
        sound(8, 9)
        say(t7.u0)

@tinmon3.on_talk
def talk():    # section 8
    if toy_tale_heard:
        sound(8, 9)
        say(t8.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 8)
