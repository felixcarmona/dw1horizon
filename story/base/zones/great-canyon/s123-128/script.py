# The Python view of script 123 of DG.SCN: screen 128 Great Canyon.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

canyon = screen(Screen.great_canyon_128)
goblimon = canyon.npc(Species.Goblimon, slot=0)
slot1 = entity(6)
slot2 = entity(7)
slot3 = canyon.npc(None, slot=3)    # the .MAP has Ogremon154 here; the script spawns what stands here
slot4 = canyon.npc(None, slot=4)    # the .MAP has Agumon here; the script spawns what stands here
slot5 = canyon.npc(None, slot=5)    # the .MAP has Agumon here; the script spawns what stands here
t5 = text.s123.sec5
t51 = text.s123.sec51
t6 = text.s123.sec6
t7 = text.s123.sec7
t81 = text.s123.sec81
t82 = text.s123.sec82

@canyon.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-150, -1850))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Pricklypear, at=(2650, 50))
    trigger(98).clear()

@goblimon.on_talk
def talk():    # section 5
    recruitable(goblimon, line=t5.u0)

@slot1.on_talk
def talk():    # section 6
    recruitable(slot1, line=t6.u0, joins=Species.Goblimon)

@slot2.on_talk
def talk():    # section 7
    recruitable(slot2, line=t7.u0, joins=Species.Goblimon)

@canyon.on_use(1)
def use1():    # section 81
    tamer.turn(1944)
    tamer.arrived()
    narrator.say(t81.u0)
    if debug_mode:
        return
    dws(r"""
        choice(narrator, open) {
            text("s123.sec81.m0.o0") => {
                canyon_bandits_active = true;
                warp_to(128, 0, 255);
                return;
            }
            text("s123.sec81.m0.o1") => {
                canyon_bandits_active = false;
                warp_to(128, 0, 255);
                return;
            }
        }
    """)

@canyon.on_use(2)
def use2():    # section 82
    tamer.turn(1944)
    tamer.arrived()
    narrator.say(t82.u0)

@canyon.on_step(0)
def step0():    # section 51
    if not canyon_bandits_active:
        return
    if canyon_bandits_beaten:
        return
    if trigger(98):
        return
    tamer.turn(1944)
    camera.to(2000, 173, speed=30)
    camera.arrived()
    tamer.say(t51.u0)
    tamer.walk(1925, 468, wait=False)
    partner.walk(1925, 78, wait=False)
    tamer.arrived()
    partner.arrived()
    load(Species.Ogremon154)
    load(Species.Agumon)
    spawn(Species.Ogremon154, slot=3)
    spawn(Species.Agumon, slot=4)
    spawn(Species.Agumon, slot=5)
    slot4.say(t51.u1)
    sound.jingle()
    slot3.say(t51.u2)
    slot5.say(t51.u3)
    wait(500)
    sound(8, 1)
    slot3.play(31)
    raw.entity_move_to(slot3, 1000, 1288, 30, 0)
    slot4.run(2067, 1561, wait=False)
    slot5.run(2059, -383, wait=False)
    slot3.arrived()
    slot4.arrived()
    slot5.arrived()
    slot3.face(tamer)
    slot4.face(tamer)
    slot5.face(tamer)
    tamer.face(slot3)
    partner.face(slot4)
    wait(500)
    sound.jingle()
    slot3.say(t51.u4)
    tamer.play(20)
    wait(750)
    tamer.say(t51.u5)
    tamer.play(anim.idle)
    slot3.say(t51.u6)
    slot3.say(t51.u7)
    slot4.say(t51.u8)
    slot4.face(slot3)
    slot3.say(t51.u9)
    slot3.face(slot4)
    fight(slot3, slot4, slot5, escape=False)
    tamer.face(slot3)
    slot3.face(tamer)
    partner.face(slot3)
    slot4.run(1350, 2350, wait=False)
    slot5.run(1850, 2350, wait=False)
    slot4.arrived()
    slot5.arrived()
    slot4.leave()
    slot5.leave()
    slot3.say(t51.u10)
    slot3.run(1650, 2350)
    slot3.leave()
    tamer.say(t51.u11)
    camera.on(tamer, speed=10)
    camera.arrived()
    canyon_bandits_beaten.set()
    canyon_cave_in.collapsed.set()
    canyon_elevator_unjammed.set()

@canyon.on_step(1)
def step1():    # section 52
    trigger(98).set()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 81, 82, 51, 52)
