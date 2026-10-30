# The Python view of script 180 of DG.SCN: screen 220 Sewer, screen 229 Mt. Infinity, screen 230 Mt. Infinity, screen 231 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sewer = screen(Screen.sewer_220)
infinity_229 = screen(Screen.mt_infinity_229)
infinity_230 = screen(Screen.mt_infinity_230)
infinity_231 = screen(Screen.mt_infinity_231)
numemon0 = sewer.npc(Species.Numemon135, slot=0)
numemon1 = sewer.npc(Species.Numemon135, slot=1)
nanimon = sewer.npc(Species.Nanimon171, slot=2)
t5 = text.s180.sec5
t52 = text.s180.sec52
t6 = text.s180.sec6
t7 = text.s180.sec7

@sewer.on_enter
def enter():    # section 254
    if not sewer_fog_seen:
        return step1()
    if factory_shut_down and not recruited(Species.Numemon):
        return numemon1.talk()

@sewer.on_step(0)
def step0():    # section 51
    tamer.walk(1482, -663)
    tamer.walk(551, 87, wait=False)
    warp(Screen.sewer_163, entry=1)

@numemon0.on_talk
def talk():    # section 5
    if not sewer_numemon_met:
        sewer_numemon_met.set()
        say(t5.u0)
        tamer.say(t5.u1)
        say(t5.u2)
        tamer.say(t5.u3)
        say(t5.u4)
        tamer.say(t5.u5)
    say(t5.u6)
    tamer.say(t5.u7)
    tamer.say(t5.u8)

@sewer.on_step(1)
def step1():    # section 52
    sewer_fog_seen.set()
    wait(1000)
    tamer.walk(1931, -482, camera=True, wait=False)
    partner.walk(1822, -891, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.say(t52.u0)
    partner.play(23)
    wait(2000)
    tamer.face(partner)
    wait(250)
    tamer.say(t52.u1)
    tamer.play(16)
    wait(1000)
    tamer.say(t52.u2)
    tamer.say(t52.u3)

@numemon1.on_talk
def talk():    # section 6
    wait(1000)
    tamer.say(t6.u0)
    camera.to(2381, -698, speed=20)
    camera.arrived()
    sound(8, 13)
    play(15)
    wait(1000)
    tamer.say(t6.u1)
    face(tamer)
    wait(500)
    sound.jingle()
    play(28)
    sound(8, 13)
    wait(2000)
    say(t6.u2)
    fight(numemon1, escape=False)
    tamer.walk(2387, -771, wait=False)
    partner.walk(1865, -772, wait=False)
    walk(2795, -771, wait=False)
    tamer.arrived()
    partner.arrived()
    arrived()
    tamer.face(numemon1)
    face(tamer)
    partner.face(numemon1)
    wait(250)
    say(t6.u3)
    tamer.say(t6.u4)
    say(t6.u5)
    tamer.say(t6.u6)
    say(t6.u7)
    tamer.say(t6.u8)
    say(t6.u9)
    raw.set_dialog_owner(tamer)
    tamer.play(19)
    wait(750)
    tamer.say(t6.u10)
    tamer.play(anim.idle)
    say(t6.u11)
    walk_away(-137, 34, looks=6, pause=500)
    send_to_city(line=t6.u12, species=Species.Numemon, sound=(8, 10))

@nanimon.on_talk
def talk():    # section 7
    wait(500)
    play(28)
    wait(500)
    tamer.say(t7.u0)
    say(t7.u1)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    run(2392, -114)
    leave()
    if key_chains == 0:
        objects[23].hide()
        tamer.run(2068, 760)
        tamer.play(12)
        wait(500)
        objects[23].show()
        sound(0, 7)
        narrator.say(t7.u2)
        sound(0, 7)
        raw.set_inventory_size(20)
        inventory_expanded.to_20.set()
    if key_chains == 4:
        objects[22].hide()
        tamer.run(2068, 760)
        tamer.play(12)
        wait(500)
        objects[22].show()
        sound(0, 7)
        narrator.say(t7.u3)
        inventory_expanded.to_30.set()
        raw.set_inventory_size(30)
        recruit(Species.Nanimon)
        engine.prosperity.add(1)
    key_chains.add(1)
    key_chain_found.sewer.set()
    return

# the section table, in the order of the original header
sections(254, 51, 5, 52, 6, 7)
