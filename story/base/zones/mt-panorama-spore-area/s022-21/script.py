# The Python view of script 22 of DG.SCN: screen 21 Mt. Panorama Spore Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.mt_panorama_spore_area_21)
slot0 = area.npc(None, slot=0)    # the .MAP has Centarumon156 here; the script spawns what stands here
slot1 = area.npc(None, slot=1)    # the .MAP has Unimon153 here; the script spawns what stands here
t5 = text.s022.sec5
t51 = text.s022.sec51

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-3450, 850))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-50, 2150))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1350, -1750))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-2450, -1450))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Happymushrm, at=(3450, 50))
    spawn_chest(Item.MedRecovery, at=(3545, 855), opened=trigger(696), facing=1024)
    spawn_chest(Item.MediumMP, at=(3545, 455), opened=trigger(697), facing=1024)
    spawn_chest(Item.Various, at=(3545, 155), opened=trigger(698), facing=1024)
    if not recruited(Species.Unimon) and centar_clinic_intro_seen:
        slot0.play(28)

@slot0.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.play(19)
    wait(1000)
    tamer.say(t5.u1)
    say(t5.u2)
    tamer.play(4)
    wait(1000)
    tamer.say(t5.u3)
    tamer.play(anim.idle)
    pick = pick_item()
    if pick is Picked.EMPTY:
        tamer.say(t5.u4)
    else:
        if engine.arg in (Item.SmRecovery, Item.MedRecovery, Item.LrgRecovery, Item.SupRecovery):
            take_picked()
        elif engine.arg in (Item.DoubleFlop, Item.Omnipotent, Item.Bandage, Item.Medicine):
            take_picked()
        else:
            tamer.say(t5.u5)
            tamer.say(t5.u14)
            say(t5.u15)
            return
        say(t5.u6)
        play(29, wait=True)
        tamer.play(25)
        wait(1000)
        tamer.say(t5.u7)
        say(t5.u8)
        tamer.play(19)
        wait(1000)
        tamer.say(t5.u9)
        say(t5.u10)
        tamer.say(t5.u11)
        say(t5.u12)
        while True:
            run(-192, -1849, wait=False)
            if glances >= 10:
                break
            glances.add(1)
            sound(8, 0)
            wait(750)
            tamer.face(slot0)
            partner.face(slot0)
        arrived()
        send_to_city(line=t5.u13, species=Species.Unimon, sound=(8, 9), prosperity=2, camera=False)
        return
    tamer.say(t5.u14)
    say(t5.u15)

@slot1.on_talk
def talk():    # section 6
    pass

@area.on_step(0)
def step0():    # section 51
    if not mystery_circles_first_seen:
        narrator.say(t51.u0)
        tamer.say(t51.u1)
        mystery_circles_first_seen.set()
        ufo_report_read.set()
        return
    if not mystery_circles_grown_seen and ufo_report_read and not vademon_encounter_ready:
        tamer.say(t51.u2)
        mystery_circles_grown_seen.set()
        vademon_encounter_ready.set()
        return
    if vademon_encounter_ready and not recruited(Species.Vademon):
        tamer.say(t51.u3)
        sound(8, 5)
        tamer.say(t51.u4)
        tamer.turn(2560)
        spawn(Species.Unimon153, slot=1)
        camera.to(-335, 285, speed=20)
        camera.arrived()
        slot1.run(1139, 1029, wait=False)
        sound(8, 5)
        slot1.arrived()
        slot1.run(-327, 459, wait=False)
        sound(8, 5)
        slot1.arrived()
        slot1.run(269, -973, wait=False)
        sound(8, 5)
        slot1.arrived()
        camera.on(tamer, speed=10)
        slot1.walk(-747, -1106, wait=False)
        sound(8, 5)
        slot1.arrived()
        slot1.face(tamer)
        narrator.say(t51.u5)
        tamer.say(t51.u6)
        slot1.say(t51.u7)
        tamer.say(t51.u8)
        slot1.say(t51.u9)
        tamer.say(t51.u10)
        slot1.say(t51.u11)
        sound(8, 6)
        wait(500)
        narrator.say(t51.u12)
        tamer.say(t51.u13)
        narrator.say(t51.u14)
        tamer.say(t51.u15)
        narrator.say(t51.u16)
        slot1.say(t51.u17)
        tamer.say(t51.u18)
        slot1.say(t51.u19)
        hide_hud()
        while True:
            slot1.run(199, -3166, wait=False)
            if glances >= 2:
                break
            glances.add(1)
            sound(8, 5)
            wait(2000)
            tamer.face(slot1)
            partner.face(slot1)
        slot1.arrived()
        slot1.leave()
        glances.set(0)
        sound(8, 9)
        narrator.say(t51.u20)
        tamer.say(t51.u21)
        recruit(Species.Vademon)
        engine.prosperity.add(3)
        return
    return

@area.on_step(10)
def step10():    # section 61
    warp(Screen.path_thru_mt_panorama_20, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 51, 61)
