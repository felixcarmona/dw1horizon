# The Python view of script 6 of DG.SCN: screen 5 Coela Point.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

point = screen(Screen.coela_point)
slot0 = point.npc(None, slot=0)    # the .MAP has Coelamon here; the script spawns what stands here
slot1 = point.npc(None, slot=1)    # the .MAP has ModokiBetamon here; the script spawns what stands here
slot2 = point.npc(None, slot=2)    # the .MAP has ModokiBetamon here; the script spawns what stands here
slot3 = point.npc(None, slot=3)    # the .MAP has ModokiBetamon here; the script spawns what stands here
slot4 = point.npc(None, slot=4)    # the .MAP has Agumon here; the script spawns what stands here
slot5 = point.npc(None, slot=5)    # the .MAP has Agumon here; the script spawns what stands here
slot6 = point.npc(None, slot=6)    # the .MAP has Coelamon here; the script spawns what stands here
slot7 = point.npc(None, slot=7)    # the .MAP has Coelamon here; the script spawns what stands here
t10 = text.s006.sec10
t51 = text.s006.sec51
t6 = text.s006.sec6
t7 = text.s006.sec7
t8 = text.s006.sec8
t9 = text.s006.sec9

@point.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.Digimushrm, at=(-750, -450))
    roll = random.roll(99)
    if roll <= 59:
        spawn_item(Item.Digimushrm, at=(-1550, 1950))
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(350, 250))
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(1950, -1050))
    if eastern_bridge_seen and not recruited(Species.Coelamon):
        objects[13].hide()
        objects[14].hide()
        objects[15].hide()
        objects[16].hide()
        objects[17].hide()
        objects[18].hide()
        objects[19].hide()
        objects[20].hide()
        objects[21].hide()
        objects[22].hide()
        objects[23].hide()
        objects[24].hide()
        objects[25].hide()
        objects[26].hide()
        objects[27].hide()
        objects[28].hide()
    if clock.hour >= 15 and clock.hour <= 19 and not recruited(Species.Coelamon):
        objects[13].hide()
        objects[14].hide()
        objects[15].hide()
        objects[16].hide()
        objects[17].hide()
        objects[18].hide()
        objects[19].hide()
        objects[20].hide()
        objects[21].hide()
        objects[22].hide()
        objects[23].hide()
        objects[24].hide()
        objects[25].hide()
        objects[26].hide()
        objects[27].hide()
        objects[28].hide()

@slot1.on_talk
def talk():    # section 6
    say(t6.u0)
    fight()

@slot2.on_talk
def talk():    # section 7
    say(t7.u0)
    fight()

@slot3.on_talk
def talk():    # section 8
    say(t8.u0)
    fight()

@slot4.on_talk
def talk():    # section 9
    say(t9.u0)
    fight()

@slot5.on_talk
def talk():    # section 10
    say(t10.u0)
    fight()

@point.on_step(0)
def step0():    # section 51
    if eastern_bridge_seen and not recruited(Species.Coelamon):
        camera.to(2214, 865, speed=20)
        camera.arrived()
        objects[13].animate(16)
        tamer.walk(1642, -107, wait=False)
        partner.run(1252, -547, wait=False)
        wait(4000)
        objects[13].show()
        objects[14].show()
        objects[15].show()
        objects[16].show()
        objects[17].show()
        objects[18].show()
        objects[19].show()
        objects[20].show()
        objects[21].show()
        objects[22].show()
        objects[23].show()
        objects[24].show()
        objects[25].show()
        objects[26].show()
        objects[27].show()
        objects[28].show()
        spawn(Species.Coelamon, slot=0)
        sound(8, 7)
        objects[31].hide()
        objects[31].animate(1)
        wait(500)
        objects[31].show()
        objects[34].hide()
        tamer.face(slot0)
        partner.face(slot0)
        wait(1000)
        slot0.face(tamer)
        slot0.say(t51.u0)
        tamer.say(t51.u1)
        slot0.say(t51.u2)
        tamer.play(19)
        wait(750)
        tamer.say(t51.u3)
        tamer.play(anim.idle)
        slot0.say(t51.u4)
        wait(500)
        objects[34].show()
        slot0.leave()
        sound(8, 7)
        objects[37].hide()
        objects[37].animate(1)
        wait(500)
        objects[37].show()
        objects[29].hide()
        objects[30].hide()
        objects[29].animate(2)
        raw.move_object_to(0, 29, 1, 30, 640, 130)
        raw.move_object_to(1, 30, 1, 30, 640, 130)
        wait(2000)
        objects[29].show()
        objects[30].show()
        wait(500)
        sound.jingle()
        narrator.say(t51.u5)
        tamer.run(1000, -461, wait=False)
        camera.on(tamer, speed=10)
        recruit(Species.Coelamon)
        engine.prosperity.add(2)
        return
    if clock.hour < 15 or clock.hour > 19 or recruited(Species.Coelamon):
        return
    camera.to(2214, 865, speed=20)
    camera.arrived()
    objects[13].animate(16)
    tamer.walk(1642, -107, wait=False)
    partner.run(1252, -547, wait=False)
    wait(4000)
    objects[13].show()
    objects[14].show()
    objects[15].show()
    objects[16].show()
    objects[17].show()
    objects[18].show()
    objects[19].show()
    objects[20].show()
    objects[21].show()
    objects[22].show()
    objects[23].show()
    objects[24].show()
    objects[25].show()
    objects[26].show()
    objects[27].show()
    objects[28].show()
    spawn(Species.Coelamon, slot=0)
    sound(8, 7)
    objects[31].hide()
    objects[31].animate(1)
    wait(500)
    objects[31].show()
    objects[34].hide()
    tamer.face(slot0)
    partner.face(slot0)
    wait(1000)
    slot0.face(tamer)
    tamer.play(15)
    wait(1000)
    if not coela_point_crossing_done:
        slot0.say(t51.u6)
        engine.no_cancel.set()
        dws(r"""
            choice(open) {
                text("s006.sec51.m0.o0") => {
                    animate(tamer, 19);
                    wait(1s);
                    engine.no_cancel = false;
                    say(slot0, text("s006.sec51.u7"));
                }
                text("s006.sec51.m0.o1") => {
                    animate(tamer, 19);
                    wait(1s);
                    engine.no_cancel = false;
                    say(slot0, text("s006.sec51.u8"));
                }
            }
        """)
        slot0.say(t51.u9)
        sound(8, 8)
        tamer.play(22)
        wait(400)
        tamer.play(22)
        wait(400)
        tamer.play(anim.idle)
        wait(150)
        sound(8, 14)
        raw.show_textbox(t51.u10)
    if coela_point_crossing_done:
        slot0.say(t51.u11)
    camera.on(slot0, speed=10)
    camera.arrived()
    objects[34].show()
    slot0.leave()
    sound(8, 7)
    objects[37].hide()
    objects[37].animate(1)
    wait(3000)
    objects[37].show()
    spawn(Species.Coelamon, slot=0)
    sound(8, 7)
    objects[31].hide()
    objects[31].animate(1)
    wait(750)
    objects[31].show()
    objects[34].hide()
    spawn(Species.Coelamon, slot=6)
    sound(8, 7)
    objects[32].hide()
    objects[32].animate(1)
    wait(750)
    objects[32].show()
    objects[35].hide()
    spawn(Species.Coelamon, slot=7)
    sound(8, 7)
    objects[33].hide()
    objects[33].animate(1)
    wait(750)
    objects[33].show()
    objects[36].hide()
    slot0.face(tamer)
    wait(1000)
    slot0.say(t51.u12)
    sound(8, 14)
    wait(500)
    sound(8, 14)
    wait(500)
    sound(8, 14)
    wait(500)
    tamer.play(anim.tamer_victory)
    wait(1000)
    tamer.say(t51.u13)
    tamer.face(slot0)
    wait(150)
    tamer.play(21)
    raw.entity_move_to(tamer, 2214, 865, 15, 0)
    wait(250)
    sound(8, 9)
    wait(600)
    sound(8, 7)
    objects[31].hide()
    objects[31].animate(1)
    tamer.face(slot6)
    wait(150)
    tamer.play(21)
    raw.entity_move_to(tamer, 2900, 1300, 14, 0)
    wait(250)
    sound(8, 9)
    wait(600)
    objects[31].show()
    sound(8, 7)
    objects[32].hide()
    objects[32].animate(1)
    tamer.face(slot7)
    wait(150)
    tamer.play(21)
    raw.entity_move_to(tamer, 3967, 3068, 15, 0)
    wait(250)
    sound(8, 9)
    wait(600)
    objects[32].show()
    sound(8, 7)
    objects[33].hide()
    objects[33].animate(1)
    tamer.face(slot7)
    wait(150)
    tamer.play(21)
    raw.entity_move_to(tamer, 5009, 4260, 15, 0)
    wait(250)
    sound(8, 9)
    wait(600)
    sound(8, 7)
    objects[33].show()
    slot0.face(tamer)
    sound(8, 7)
    objects[31].hide()
    objects[31].animate(1)
    wait(750)
    objects[31].show()
    slot6.face(tamer)
    slot7.face(tamer)
    wait(1000)
    slot0.say(t51.u14)
    sound(8, 14)
    coela_point_crossing_done.set()
    partner.walk(3500, 2500, wait=False)
    warp(Screen.tropical_jungle_12, entry=4)

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 10, 51)
