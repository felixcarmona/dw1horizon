# The Python view of script 68 of DG.SCN: screen 71 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_71)
elecmon = savanna.npc(Species.Elecmon140, slot=0)
akatorimon1 = savanna.npc(Species.Akatorimon, slot=1)
akatorimon2 = savanna.npc(Species.Akatorimon, slot=2)
shamamon = savanna.npc(Species.Shamamon, slot=3)
psychemon4 = savanna.npc(Species.Psychemon, slot=4)
psychemon5 = savanna.npc(Species.Psychemon, slot=5)
slot6 = entity(11)
t10 = text.s068.sec10
t11 = text.s068.sec11
t5 = text.s068.sec5
t51 = text.s068.sec51
t6 = text.s068.sec6
t7 = text.s068.sec7
t8 = text.s068.sec8
t9 = text.s068.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(750, -1150))
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(-1450, 650))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.SweetNut, at=(-1050, 3150))
    if factorial_town_reopened:
        return
    objects[38].show()
    objects[39].show()
    objects[40].show()

@elecmon.on_talk
def talk():    # section 5
    match pstat(33):
        case 0:
            wait(50)
            damage_percent.set(20)
            raw.deal_damage(damage_percent)
            objects[41].hide()
            objects[41].animate(1)
            raw.spawn_sprite_at_entity(elecmon, 2, 41)
            sound(8, 0)
            partner.play(40)
            wait(150)
            tamer.play(17)
            face(tamer)
            arrived()
            objects[41].show()
            objects[42].show()
            say(t5.u0)
            camera.on(tamer, speed=10)
            camera.arrived()
            pstat(33).add(1)
        case 1:
            wait(50)
            damage_percent.set(20)
            raw.deal_damage(damage_percent)
            objects[41].hide()
            objects[41].animate(1)
            raw.spawn_sprite_at_entity(elecmon, 2, 41)
            sound(8, 0)
            partner.play(40)
            wait(150)
            tamer.play(17)
            face(tamer)
            arrived()
            objects[41].show()
            objects[42].show()
            say(t5.u1)
            camera.on(tamer, speed=10)
            camera.arrived()
            pstat(33).add(1)
        case 2 | _:
            wait(50)
            damage_percent.set(20)
            raw.deal_damage(damage_percent)
            objects[41].hide()
            objects[41].animate(1)
            raw.spawn_sprite_at_entity(elecmon, 2, 41)
            sound(8, 0)
            partner.play(40)
            wait(150)
            tamer.play(17)
            face(tamer)
            arrived()
            objects[41].show()
            objects[42].show()
            camera.on(tamer, speed=10)
            camera.arrived()
            say(t5.u2)
            tamer.play(19)
            tamer.say(t5.u3)
            say(t5.u4)
            walk_away(-171, -2105, looks=6, pause=500)
            send_to_city(line=t5.u5, species=Species.Elecmon, sound=(8, 5), camera=False)
            camera.on(tamer, speed=10)
            camera.arrived()

@akatorimon1.on_talk
def talk():    # section 6
    recruitable(akatorimon1, line=t6.u0)

@akatorimon2.on_talk
def talk():    # section 7
    recruitable(akatorimon2, line=t7.u0)

@shamamon.on_talk
def talk():    # section 8
    recruitable(shamamon, line=t8.u0)

@psychemon4.on_talk
def talk():    # section 9
    recruitable(psychemon4, line=t9.u0)

@psychemon5.on_talk
def talk():    # section 10
    recruitable(psychemon5, line=t10.u0)

@slot6.on_talk
def talk():    # section 11
    recruitable(slot6, line=t11.u0, joins=Species.Akatorimon)

@savanna.on_step(0)
def step0():    # section 51
    if factorial_town_reopened:
        tamer.walk(1020, 4048, wait=False)
        warp(Screen.factorial_town_156, entry=1)
    tamer.turn(2048)
    wait(500)
    tamer.say(t51.u0)
    tamer.run(946, 2852, camera=True)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 51)
