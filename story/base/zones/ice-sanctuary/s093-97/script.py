# The Python view of script 93 of DG.SCN: screen 97 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sanctuary = screen(Screen.ice_sanctuary_97)
slot0 = sanctuary.npc(None, slot=0)    # the .MAP has Angemon142 here; the script spawns what stands here
t5 = text.s093.sec5
t51 = text.s093.sec51
t52 = text.s093.sec52

@sanctuary.on_enter
def enter():    # section 254
    if angemon_voice_heard:
        objects[7].show()
    call(Routine.spawn_angemon_pedestal)
    if angemon_pedestal_raised:
        call(Routine.raise_angemon_pedestal)

@sanctuary.on_step(0)
def step0():    # section 51
    if angemon_pedestal_raised:
        warp(Screen.ice_sanctuary_98, entry=0)
        return
    if not trigger(324):
        tamer.turn(2048)
        wait(250)
        tamer.play(23)
        wait(250)
        tamer.say(t51.u0)
        tamer.say(t51.u1)
        tamer.play(anim.idle)
        trigger(324).set()
        return

@sanctuary.on_step(1)
def step1():    # section 52
    if angemon_voice_heard and recruited(Species.Angemon):
        return slot0.talk()
    if not angemon_pedestal_raised and trigger(324):
        partner.walk(50, 1050)
        wait(500)
        tamer.face(partner)
        tamer.say(t52.u0)
        call(Routine.raise_angemon_pedestal)
        wait(1000)
        tamer.say(t52.u1)
        angemon_pedestal_raised.set()
        return

@slot0.on_talk
def talk():    # section 5
    if recruited(Species.Angemon):
        return
    tamer.turn(2048)
    wait(1000)
    tamer.turn(1536)
    wait(500)
    tamer.turn(2560)
    wait(1000)
    tamer.say(t5.u0)
    tamer.turn(2048)
    tamer.play(23)
    wait(1000)
    camera.to(-831, 2975, speed=20)
    camera.arrived()
    tamer.say(t5.u1)
    load(Species.Angemon142)
    spawn(Species.Angemon142, slot=0)
    sound(8, 10)
    play(28)
    wait(3000)
    play(anim.idle)
    say(t5.u2)
    tamer.say(t5.u3)
    say(t5.u4)
    tamer.say(t5.u5)
    say(t5.u6)
    tamer.say(t5.u7)
    say(t5.u8)
    tamer.say(t5.u9)
    say(t5.u10)
    tamer.say(t5.u11)
    walk_away(47, -2650, looks=3)
    send_to_city(line=t5.u12, species=Species.Angemon, prosperity=2, camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5)
