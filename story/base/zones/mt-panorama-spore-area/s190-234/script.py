# The Python view of script 190 of DG.SCN: screen 234 Mt. Panorama Spore Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.mt_panorama_spore_area_234)
slot0 = area.npc(None, slot=0)    # the .MAP has Vademon150 here; the script spawns what stands here
t51 = text.s190.sec51

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-1050, 250))
        spawn_item(Item.Digimushrm, at=(-1050, 450))
        spawn_item(Item.Digimushrm, at=(-1050, 50))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-550, -1650))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Happymushrm, at=(950, 750))
    spawn_chest(Item.MedRecovery, at=(938, 1239), opened=trigger(696), facing=1024)
    spawn_chest(Item.MediumMP, at=(985, 856), opened=trigger(697), facing=1024)
    spawn_chest(Item.Various, at=(1024, -1604), opened=trigger(698), facing=1024)
    if ufo_report_read:
        objects[6].hide()
        objects[7].hide()
        objects[8].hide()
        objects[9].hide()
    if vademon_encounter_ready:
        objects[10].hide()
        objects[11].hide()
        objects[12].hide()
        objects[13].hide()
        objects[14].hide()
        objects[15].hide()
        objects[16].hide()
        objects[17].hide()
        objects[18].hide()

@area.on_step(1)
def step1():    # section 52
    if not mystery_circles_grown_seen and ufo_report_read and not vademon_encounter_ready:
        return L13()
    if vademon_encounter_ready and not recruited(Species.Vademon):
        return L14()
    return L17()

@area.on_step(0)
def step0():    # section 51
    if not mystery_circles_first_seen:
        narrator.say(t51.u0)
        tamer.say(t51.u1)
        mystery_circles_first_seen.set()
        return
    if not mystery_circles_grown_seen and ufo_report_read and not vademon_encounter_ready:
        return L13()
    if vademon_encounter_ready and not recruited(Species.Vademon):
        return L14()
    return L17()

def L13():    # shared code (the disc's label L13)
    tamer.walk(350, -50, camera=True)
    tamer.play(24)
    wait(1000)
    tamer.say(t51.u2)
    mystery_circles_grown_seen.set()

def L14():    # shared code (the disc's label L14)
    tamer.run(350, 50, camera=True)
    tamer.play(24)
    wait(1000)
    tamer.say(t51.u3)
    tamer.run(-550, 50, camera=True)
    tamer.say(t51.u4)
    tamer.play(16)
    wait(1000)
    tamer.say(t51.u5)
    sound(8, 5)
    tamer.say(t51.u6)
    spawn(Species.Vademon150, slot=0)
    tamer.face(slot0)
    partner.run(-750, -50, wait=False)
    camera.to(-183, 723, speed=20)
    camera.arrived()
    partner.arrived()
    slot0.run(225, 1066, wait=False)
    sound(8, 5)
    slot0.arrived()
    slot0.walk(-275, 1066, wait=False)
    sound(8, 5)
    slot0.arrived()
    slot0.walk(-63, 453, wait=False)
    sound(8, 5)
    slot0.arrived()
    slot0.walk(-126, 409, wait=False)
    tamer.face(slot0)
    wait(1000)
    tamer.say(t51.u7)
    slot0.say(t51.u8)
    tamer.say(t51.u9)
    slot0.say(t51.u10)
    tamer.say(t51.u11)
    slot0.say(t51.u12)
    sound(8, 6)
    wait(500)
    slot0.play(28)
    wait(500)
    tamer.play(15)
    wait(500)
    tamer.say(t51.u13)
    wait(2000)
    slot0.play(anim.idle)
    tamer.say(t51.u14)
    tamer.play(19)
    wait(1000)
    narrator.say(t51.u15)
    slot0.say(t51.u16)
    tamer.say(t51.u17)
    slot0.play(22)
    wait(750)
    slot0.play(22)
    wait(750)
    slot0.play(anim.idle)
    slot0.say(t51.u18)
    hide_hud()
    while True:
        slot0.run(155, -1177, wait=False)
        if glances >= 3:
            break
        glances.add(1)
        sound(8, 5)
        wait(1000)
        tamer.face(slot0)
        partner.face(slot0)
    slot0.arrived()
    slot0.leave()
    glances.set(0)
    sound(8, 8)
    narrator.say(t51.u19)
    tamer.say(t51.u20)
    recruit(Species.Vademon)
    engine.prosperity.add(3)
    camera.on(tamer, speed=10)
    camera.arrived()

def L17():    # shared code (the disc's label L17)
    return

# the section table, in the order of the original header
sections(254, 52, 51)
