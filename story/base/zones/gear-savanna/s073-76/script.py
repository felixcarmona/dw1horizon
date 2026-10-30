# The Python view of script 73 of DG.SCN: screen 76 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_76)
slot0 = savanna.npc(None, slot=0)    # the .MAP has Patamon151 here; the script spawns what stands here
slot1 = savanna.npc(None, slot=1)    # the .MAP has Goblimon125 here; the script spawns what stands here
slot2 = savanna.npc(None, slot=2)    # the .MAP has Leomon166 here; the script spawns what stands here
shamamon3 = savanna.npc(Species.Shamamon, slot=3)
shamamon4 = savanna.npc(Species.Shamamon, slot=4)
t51 = text.s073.sec51
t8 = text.s073.sec8
t9 = text.s073.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(-1050, -950))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1250, -3950))
    roll = random.roll(99)
    if roll <= 11:
        spawn_item(Item.Digimushrm, at=(-950, 2550))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Digimushrm, at=(1150, 1450))
    trigger(338).clear()

@savanna.on_step(0)
def step0():    # section 51
    if leomon_rescue_seen or trigger(338):
        return
    tamer.turn(2048)
    partner.turn(2048)
    wait(250)
    leomon_rescue_seen.set()
    spawn(Species.Patamon151, slot=0)
    spawn(Species.Goblimon125, slot=1)
    camera.to(-205, 1478, speed=15)
    camera.arrived()
    slot0.run(-254, 439, wait=False)
    slot1.run(-254, 1039, wait=False)
    wait(2250)
    slot0.turn(0)
    slot1.turn(0)
    camera.on(slot0, speed=25)
    camera.arrived()
    tamer.say(t51.u0)
    slot0.arrived()
    slot0.face(tamer)
    wait(250)
    slot0.say(t51.u1)
    tamer.play(7)
    wait(750)
    tamer.say(t51.u2)
    tamer.play(anim.idle)
    tamer.run(-150, -550, wait=False)
    partner.run(-80, -300, wait=False)
    narrator.say(t51.u3)
    engine.music_mode.set(3)
    music(11)
    spawn(Species.Leomon166, slot=2)
    camera.to(-677, 509, speed=20)
    camera.arrived()
    slot2.face(slot1)
    tamer.face(slot2)
    wait(500)
    tamer.say(t51.u4)
    slot0.face(slot2)
    slot1.face(slot2)
    wait(500)
    slot2.face(slot1)
    slot1.run(-254, 1039, wait=False)
    wait(250)
    raw.entity_move_to_axis(slot2, 0, 1, 1)
    wait(100)
    slot2.play(28)
    wait(1000)
    slot2.play(anim.idle)
    sound(8, 1)
    tamer.face(slot2)
    slot0.face(slot2)
    slot1.face(slot2)
    tamer.arrived()
    slot0.arrived()
    slot1.arrived()
    slot1.play(40)
    wait(1000)
    slot1.run(0, 4000)
    slot1.leave()
    slot0.face(slot2)
    wait(250)
    slot2.face(slot0)
    wait(250)
    slot2.say(t51.u5)
    slot0.say(t51.u6)
    slot2.say(t51.u7)
    slot2.run(-2323, 1264, wait=False)
    wait(1000)
    slot0.say(t51.u8)
    slot0.run(-2323, 1264, wait=False)
    wait(2000)
    slot0.arrived()
    slot2.arrived()
    slot2.leave()
    slot0.leave()
    camera.on(tamer, speed=10)
    camera.arrived()
    tamer.say(t51.u9)
    tamer.play(anim.idle)
    leomon_rescue_seen.set()

@savanna.on_step(1)
def step1():    # section 52
    trigger(338).set()

@shamamon3.on_talk
def talk():    # section 8
    recruitable(shamamon3, line=t8.u0)

@shamamon4.on_talk
def talk():    # section 9
    recruitable(shamamon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 8, 9)
