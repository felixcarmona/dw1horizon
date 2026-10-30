# The Python view of script 18 of DG.SCN: screen 17 Amida Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

forest = screen(Screen.amida_forest)
slot0 = forest.npc(None, slot=0)    # the .MAP has Centarumon156 here; the script spawns what stands here
slot1 = forest.npc(None, slot=1)    # the .MAP has Centarumon156 here; the script spawns what stands here
slot2 = forest.npc(None, slot=2)    # the .MAP has Centarumon156 here; the script spawns what stands here
slot5 = forest.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
t10 = text.s018.sec10
t51 = text.s018.sec51
t68 = text.s018.sec68
t69 = text.s018.sec69
t70 = text.s018.sec70

@forest.on_enter
def enter():    # section 254
    call(Routine.save_clock_speed, arg=0)
    if recruited(Species.Centarumon):
        return
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.GiantMeat, at=(-1650, 50))
    elif roll <= 49:
        spawn_item(Item.OffDisk, at=(-1650, 50))
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.MPFloppy, at=(-50, -350))
    elif roll <= 49:
        spawn_item(Item.SmRecovery, at=(-50, -350))
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.DefDisk, at=(1750, 750))
    elif roll <= 49:
        spawn_item(Item.Meat, at=(1750, 750))
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.PortPotty, at=(-1550, 2050))
    elif roll <= 29:
        spawn_item(Item.HispeedDsk, at=(-1550, 2050))
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.MedRecovery, at=(50, 1550))
    elif roll <= 29:
        spawn_item(Item.MoldyMeat, at=(50, 1550))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.OrangeBana, at=(-50, 3150))
    elif roll <= 9:
        spawn_item(Item.Happymushrm, at=(-50, 3150))
    elif roll <= 29:
        spawn_item(Item.AutoPilot, at=(-50, 3150))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.OmniDisk, at=(1550, 2750))
        return
    if roll <= 29:
        spawn_item(Item.MediumMP, at=(1550, 2750))

@forest.on_step(0)
def step0():    # section 51
    objects[38].show()
    objects[39].show()
    objects[40].show()
    objects[41].show()
    objects[42].show()
    objects[43].show()
    if recruited(Species.Centarumon):
        return
    roll = random.roll(2)
    if roll == 0:
        amida_correct_path.set(0)
        objects[38].hide()
        objects[42].hide()
        objects[43].hide()
    if roll == 1:
        amida_correct_path.set(1)
        objects[39].hide()
        objects[41].hide()
        objects[43].hide()
    if roll == 2:
        amida_correct_path.set(2)
        objects[40].hide()
        objects[41].hide()
        objects[42].hide()
    if not amida_forest_warning_heard:
        amida_forest_warning_heard.set()
        tamer.turn(2048)
        sound(8, 0)
        wait(1000)
        sound(8, 0)
        wait(1000)
        sound(8, 0)
        wait(1000)
        narrator.say(t51.u0)
    slot5.talk()

@slot5.on_talk
def talk():    # section 10
    amida_path_passed.zone1.clear()
    amida_path_passed.zone2.clear()
    amida_path_passed.zone3.clear()
    amida_path_passed.zone4.clear()
    amida_path_passed.zone5.clear()
    amida_path_passed.zone6.clear()
    amida_path_passed.zone7.clear()
    amida_path_passed.zone8.clear()
    amida_path_passed.zone9.clear()
    amida_path_passed.zone10.clear()
    amida_path_passed.zone11.clear()
    amida_path_passed.zone12.clear()
    amida_path_passed.zone13.clear()
    amida_path_passed.zone14.clear()
    amida_path_passed.zone15.clear()
    amida_path_passed.zone16.clear()
    raw.jump_return()

@forest.on_step(1)
def step1():    # section 52
    if recruited(Species.Centarumon):
        return
    L24()
    amida_path_passed.zone1.set()
    amida_path_passed.zone2.clear()
    amida_path_passed.zone3.clear()
    if not amida_path_passed.zone4:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 109, 428)
    raw.move_object_to(1, 47, 1, 0, 109, 432)
    raw.move_object_to(2, 48, 1, 0, 109, 436)
    wait(50)
    raw.move_object_to(0, 46, 1, 10, 52, 765)
    raw.move_object_to(1, 47, 1, 10, 52, 769)
    raw.move_object_to(2, 48, 1, 10, 52, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    tamer.play(17)
    raw.entity_move_to_axis_with_camera(tamer, -3800, 2, 10)
    wait(2000)
    L27()
    camera.on(tamer, speed=10)
    camera.arrived()
    slot5.talk()
    L22()

@forest.on_step(2)
def step2():    # section 53
    if recruited(Species.Centarumon):
        return
    L24()
    amida_path_passed.zone2.set()
    amida_path_passed.zone1.clear()
    amida_path_passed.zone3.clear()
    if not amida_path_passed.zone5:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 430)
    raw.move_object_to(1, 47, 1, 0, 300, 434)
    raw.move_object_to(2, 48, 1, 0, 300, 438)
    wait(50)
    raw.move_object_to(0, 46, 1, 10, 300, 765)
    raw.move_object_to(1, 47, 1, 10, 300, 769)
    raw.move_object_to(2, 48, 1, 10, 300, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    tamer.play(17)
    raw.entity_move_to_axis_with_camera(tamer, -3800, 2, 10)
    wait(2000)
    L27()
    camera.on(tamer, speed=10)
    camera.arrived()
    slot5.talk()
    L22()

@forest.on_step(3)
def step3():    # section 54
    if recruited(Species.Centarumon):
        return
    L24()
    amida_path_passed.zone3.set()
    amida_path_passed.zone1.clear()
    amida_path_passed.zone2.clear()
    if not amida_path_passed.zone7:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 495, 430)
    raw.move_object_to(1, 47, 1, 0, 495, 434)
    raw.move_object_to(2, 48, 1, 0, 495, 438)
    wait(50)
    raw.move_object_to(0, 46, 1, 10, 540, 765)
    raw.move_object_to(1, 47, 1, 10, 540, 769)
    raw.move_object_to(2, 48, 1, 10, 540, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    tamer.play(17)
    raw.entity_move_to_axis_with_camera(tamer, -3800, 2, 10)
    wait(2000)
    L27()
    camera.on(tamer, speed=10)
    camera.arrived()
    slot5.talk()
    L22()

@forest.on_step(4)
def step4():    # section 55
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone4.set()
    roll = random.roll(1)
    if not amida_path_passed.zone8:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 135, 215)
    raw.move_object_to(1, 47, 1, 0, 135, 219)
    raw.move_object_to(2, 48, 1, 0, 135, 223)
    wait(50)
    raw.move_object_to(0, 46, 1, 17, 52, 765)
    raw.move_object_to(1, 47, 1, 17, 52, 769)
    raw.move_object_to(2, 48, 1, 17, 52, 773)
    wait(250)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -3800, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(5)
def step5():    # section 56
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone5.set()
    roll = random.roll(1)
    if not amida_path_passed.zone6:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 225)
    raw.move_object_to(1, 47, 1, 0, 300, 229)
    raw.move_object_to(2, 48, 1, 0, 300, 233)
    wait(50)
    raw.move_object_to(0, 46, 1, 17, 300, 765)
    raw.move_object_to(1, 47, 1, 17, 300, 769)
    raw.move_object_to(2, 48, 1, 17, 300, 773)
    wait(250)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -3800, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(6)
def step6():    # section 57
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone6.set()
    roll = random.roll(1)
    if not amida_path_passed.zone2 or not amida_path_passed.zone5:
        if not amida_path_passed.zone9:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 200)
    raw.move_object_to(1, 47, 1, 0, 300, 204)
    raw.move_object_to(2, 48, 1, 0, 300, 208)
    wait(50)
    raw.move_object_to(0, 46, 1, 19, 300, 765)
    raw.move_object_to(1, 47, 1, 19, 300, 769)
    raw.move_object_to(2, 48, 1, 19, 300, 773)
    wait(200)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -1000, 2, 5)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(7)
def step7():    # section 58
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone7.set()
    roll = random.roll(1)
    if not amida_path_passed.zone12:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 470, 225)
    raw.move_object_to(1, 47, 1, 0, 470, 229)
    raw.move_object_to(2, 48, 1, 0, 470, 223)
    wait(50)
    raw.move_object_to(0, 46, 1, 19, 540, 765)
    raw.move_object_to(1, 47, 1, 19, 540, 769)
    raw.move_object_to(2, 48, 1, 19, 540, 773)
    wait(200)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -3650, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(8)
def step8():    # section 59
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone8.set()
    roll = random.roll(1)
    if not amida_path_passed.zone1 or not amida_path_passed.zone4:
        if not amida_path_passed.zone10:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 150, 95)
    raw.move_object_to(1, 47, 1, 0, 150, 99)
    raw.move_object_to(2, 48, 1, 0, 150, 103)
    wait(50)
    raw.move_object_to(0, 46, 1, 21, 52, 765)
    raw.move_object_to(1, 47, 1, 21, 52, 769)
    raw.move_object_to(2, 48, 1, 21, 52, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -400, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(9)
def step9():    # section 60
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone9.set()
    roll = random.roll(1)
    if not amida_path_passed.zone6 or not amida_path_passed.zone5:
        if not amida_path_passed.zone11:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 95)
    raw.move_object_to(1, 47, 1, 0, 300, 99)
    raw.move_object_to(2, 48, 1, 0, 300, 103)
    wait(50)
    raw.move_object_to(0, 46, 1, 21, 300, 765)
    raw.move_object_to(1, 47, 1, 21, 300, 769)
    raw.move_object_to(2, 48, 1, 21, 300, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -1100, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2600, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(10)
def step10():    # section 61
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone10.set()
    roll = random.roll(1)
    if not amida_path_passed.zone4 or not amida_path_passed.zone8:
        if not amida_path_passed.zone14:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 165, 0)
    raw.move_object_to(1, 47, 1, 0, 165, 4)
    raw.move_object_to(2, 48, 1, 0, 165, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 25, 52, 765)
    raw.move_object_to(1, 47, 1, 25, 52, 769)
    raw.move_object_to(2, 48, 1, 25, 52, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 2000, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 0, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(11)
def step11():    # section 62
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone11.set()
    roll = random.roll(1)
    if not amida_path_passed.zone6 or not amida_path_passed.zone9:
        if not amida_path_passed.zone13:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 0)
    raw.move_object_to(1, 47, 1, 0, 300, 4)
    raw.move_object_to(2, 48, 1, 0, 300, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 25, 300, 765)
    raw.move_object_to(1, 47, 1, 25, 300, 769)
    raw.move_object_to(2, 48, 1, 25, 300, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    tamer.play(17)
    raw.entity_move_to_axis_with_camera(tamer, 1400, 2, 10)
    wait(2000)
    L27()
    slot5.talk()
    camera.on(tamer, speed=10)
    camera.arrived()
    L22()

@forest.on_step(12)
def step12():    # section 63
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone12.set()
    roll = random.roll(1)
    if not amida_path_passed.zone3 or not amida_path_passed.zone7:
        if not amida_path_passed.zone16:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 445, 0)
    raw.move_object_to(1, 47, 1, 0, 445, 4)
    raw.move_object_to(2, 48, 1, 0, 445, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 25, 540, 765)
    raw.move_object_to(1, 47, 1, 25, 540, 769)
    raw.move_object_to(2, 48, 1, 25, 540, 773)
    wait(250)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 800, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -2000, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(13)
def step13():    # section 64
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone13.set()
    roll = random.roll(1)
    if not amida_path_passed.zone9 or not amida_path_passed.zone11:
        if not amida_path_passed.zone15:
            return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 0)
    raw.move_object_to(1, 47, 1, 0, 300, 4)
    raw.move_object_to(2, 48, 1, 0, 300, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 29, 300, 765)
    raw.move_object_to(1, 47, 1, 29, 300, 769)
    raw.move_object_to(2, 48, 1, 29, 300, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    tamer.play(17)
    raw.entity_move_to_axis_with_camera(tamer, 1500, 2, 10)
    wait(2000)
    L27()
    slot5.talk()
    camera.on(tamer, speed=10)
    camera.arrived()
    L22()

@forest.on_step(14)
def step14():    # section 65
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone14.set()
    roll = random.roll(1)
    if not amida_path_passed.zone8 or not amida_path_passed.zone10:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 158, 0)
    raw.move_object_to(1, 47, 1, 0, 158, 4)
    raw.move_object_to(2, 48, 1, 0, 158, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 29, 25, 765)
    raw.move_object_to(1, 47, 1, 29, 25, 769)
    raw.move_object_to(2, 48, 1, 29, 25, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 1800, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -400, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(15)
def step15():    # section 66
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone15.set()
    roll = random.roll(1)
    if not amida_path_passed.zone13 or not amida_path_passed.zone11:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 300, 0)
    raw.move_object_to(1, 47, 1, 0, 300, 4)
    raw.move_object_to(2, 48, 1, 0, 300, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 29, 300, 765)
    raw.move_object_to(1, 47, 1, 29, 300, 769)
    raw.move_object_to(2, 48, 1, 29, 300, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 2550, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 1400, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(16)
def step16():    # section 67
    if recruited(Species.Centarumon):
        return
    amida_path_passed.zone16.set()
    roll = random.roll(1)
    if not amida_path_passed.zone12 or not amida_path_passed.zone7:
        return
    tamer.turn(2048)
    partner.turn(2048)
    L26()
    sound(8, 2)
    sound(8, 2)
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[46].animate(3)
    raw.move_object_to(0, 46, 1, 0, 445, 0)
    raw.move_object_to(1, 47, 1, 0, 445, 4)
    raw.move_object_to(2, 48, 1, 0, 445, 8)
    wait(50)
    raw.move_object_to(0, 46, 1, 25, 540, 765)
    raw.move_object_to(1, 47, 1, 25, 540, 769)
    raw.move_object_to(2, 48, 1, 25, 540, 773)
    wait(150)
    partner.play(40)
    damage_percent.set(50)
    raw.deal_damage(damage_percent)
    if roll == 0:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, 1000, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    else:
        tamer.play(17)
        raw.entity_move_to_axis_with_camera(tamer, -1800, 2, 10)
        wait(2000)
        L27()
        slot5.talk()
        camera.on(tamer, speed=10)
        camera.arrived()
    L22()

@forest.on_step(17)
def step17():    # section 68
    if recruited(Species.Centarumon):
        return
    if amida_correct_path == 0:
        tamer.say(t68.u0)
        sound(8, 2)
        wait(1000)
        objects[38].show()
        tamer.run(-1750, 3600, camera=True, wait=False)
        partner.run(-1450, 3600)
        tamer.arrived()
        tamer.turn(2048)
        partner.turn(2048)
        spawn(Species.Centarumon156, slot=0)
        slot0.walk(-1600, 4300)
        slot0.say(t68.u1)
        recruit(Species.Centarumon)
        engine.prosperity.add(2)
        slot0.say(t68.u2)
        slot0.walk_away(-1600, 1000, looks=4)
        slot0.leave()
        glances.set(0)
        sound(8, 9)
        narrator.say(t68.u3)
        camera.on(tamer, speed=10)
        camera.arrived()
        tamer.face(partner)
        partner.face(tamer)
        wait(250)
        tamer.say(t68.u4)
        tamer.play(anim.tamer_victory)
        tamer.say(t68.u5)
        tamer.walk(-1600, 5200, wait=False)
        wait(1000)
        partner.walk(-1600, 5200, wait=False)
        wait(1000)
        warp(Screen.ancient_dino_region, entry=0)
        return
    sound(0, 11)
    narrator.say(t68.u6)
    warp(Screen.amida_forest, entry=0)

@forest.on_step(18)
def step18():    # section 69
    if recruited(Species.Centarumon):
        return
    if amida_correct_path == 1:
        tamer.say(t69.u0)
        sound(8, 2)
        wait(1000)
        objects[39].show()
        tamer.run(-241, 3600, camera=True, wait=False)
        partner.run(200, 3600)
        tamer.arrived()
        tamer.turn(2048)
        partner.turn(2048)
        spawn(Species.Centarumon156, slot=1)
        slot1.walk(0, 4300)
        slot1.say(t69.u1)
        recruit(Species.Centarumon)
        engine.prosperity.add(2)
        slot1.say(t69.u2)
        slot1.walk_away(0, 1000, looks=4)
        slot1.leave()
        glances.set(0)
        sound(8, 9)
        narrator.say(t69.u3)
        camera.on(tamer, speed=10)
        camera.arrived()
        tamer.face(partner)
        partner.face(tamer)
        wait(250)
        tamer.say(t69.u4)
        tamer.play(anim.tamer_victory)
        tamer.say(t69.u5)
        tamer.walk(0, 5200, wait=False)
        wait(1000)
        partner.walk(0, 5200, wait=False)
        wait(1000)
        warp(Screen.ancient_dino_region, entry=0)
        return
    sound(0, 11)
    narrator.say(t69.u6)
    warp(Screen.amida_forest, entry=0)

@forest.on_step(19)
def step19():    # section 70
    if recruited(Species.Centarumon):
        return
    if amida_correct_path == 2:
        tamer.say(t70.u0)
        sound(8, 2)
        wait(1000)
        objects[40].show()
        tamer.run(1450, 3600, camera=True, wait=False)
        partner.run(1667, 3600)
        tamer.arrived()
        tamer.turn(2048)
        partner.turn(2048)
        spawn(Species.Centarumon156, slot=2)
        slot2.walk(1600, 4300)
        slot2.say(t70.u1)
        recruit(Species.Centarumon)
        engine.prosperity.add(2)
        slot2.say(t70.u2)
        slot2.walk_away(1600, 1000, looks=4)
        slot2.leave()
        glances.set(0)
        sound(8, 9)
        narrator.say(t70.u3)
        camera.on(tamer, speed=10)
        camera.arrived()
        tamer.face(partner)
        partner.face(tamer)
        wait(250)
        tamer.say(t70.u4)
        tamer.play(anim.tamer_victory)
        tamer.say(t70.u5)
        tamer.walk(1600, 5200, wait=False)
        wait(1000)
        partner.walk(1600, 5200, wait=False)
        wait(1000)
        warp(Screen.ancient_dino_region, entry=0)
        return
    sound(0, 11)
    narrator.say(t70.u6)
    warp(Screen.amida_forest, entry=0)

@slot0.on_talk
def talk():    # section 5
    pass

@slot1.on_talk
def talk():    # section 6
    pass

@forest.on_step(20)
def step20():    # section 71
    tamer.walk(-1600, 5200, wait=False)
    warp(Screen.ancient_dino_region, entry=0)

@forest.on_step(21)
def step21():    # section 72
    tamer.walk(0, 5200, wait=False)
    warp(Screen.ancient_dino_region, entry=0)

@forest.on_step(22)
def step22():    # section 73
    tamer.walk(1600, 5200, wait=False)
    warp(Screen.ancient_dino_region, entry=0)
    return

def L22():    # shared code (the disc's label L22)
    if partner.hp == 1:
        tamer.face(partner)
        tamer.say(t10.u0)
        warp(Screen.amida_forest, entry=0, then=51)
    raw.jump_return()

def L24():    # shared code (the disc's label L24)
    if partner.hp == 1:
        tamer.face(partner)
        tamer.say(t10.u1)
        warp(Screen.amida_forest, entry=0, then=51)
    raw.jump_return()

def L26():    # shared code (the disc's label L26)
    sound(8, 1)
    objects[44].hide()
    objects[45].hide()
    raw.spawn_sprite_at_entity(tamer, 10, 44)
    raw.spawn_sprite_at_entity(tamer, 10, 45)
    wait(200)
    objects[44].show()
    objects[45].show()
    wait(200)
    objects[44].hide()
    objects[45].hide()
    raw.spawn_sprite_at_entity(tamer, 10, 44)
    raw.spawn_sprite_at_entity(tamer, 10, 45)
    wait(200)
    objects[44].show()
    objects[45].show()
    wait(200)
    objects[44].hide()
    objects[45].hide()
    raw.spawn_sprite_at_entity(tamer, 10, 44)
    raw.spawn_sprite_at_entity(tamer, 10, 45)
    wait(200)
    objects[44].show()
    objects[45].show()
    wait(500)
    raw.jump_return()

def L27():    # shared code (the disc's label L27)
    objects[46].show()
    objects[47].show()
    objects[48].show()
    raw.move_object_to(0, 46, 1, 0, 600, 900)
    raw.move_object_to(1, 47, 1, 0, 600, 900)
    raw.move_object_to(2, 48, 1, 0, 600, 900)
    wait(50)
    raw.jump_return()

# the section table, in the order of the original header
sections(254, 51, 10, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 5, 6, 71, 72, 73)
