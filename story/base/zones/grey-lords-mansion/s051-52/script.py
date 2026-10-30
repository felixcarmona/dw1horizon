# The Python view of script 51 of DG.SCN: screen 52 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_52)
slot0 = mansion.npc(None, slot=0)    # the .MAP has Devimon here; the script spawns what stands here
t57 = text.s051.sec57
t81 = text.s051.sec81
t82 = text.s051.sec82
t84 = text.s051.sec84
t85 = text.s051.sec85

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_step(6)
def step6():    # section 57
    if myotismon_absence_seen.mansion and myotismon_absence_seen.basement and not mansion_devimon_met:
        mansion_devimon_met.set()
        load(Species.Devimon)
        spawn(Species.Devimon, slot=0)
        raw.set_dialog_owner(tamer)
        tamer.play(25)
        wait(750)
        tamer.say(t57.u0)
        tamer.play(anim.idle)
        tamer.face(slot0)
        wait(500)
        camera.to(0, 1614, speed=20)
        camera.arrived()
        slot0.say(t57.u1)
        tamer.run(-150, -239, wait=False)
        partner.run(150, -239, wait=False)
        tamer.arrived()
        partner.arrived()
        tamer.face(slot0)
        partner.face(slot0)
        wait(250)
        tamer.say(t57.u2)
        slot0.say(t57.u3)
        tamer.say(t57.u4)
        slot0.say(t57.u5)
        tamer.play(20)
        wait(750)
        tamer.say(t57.u6)
        tamer.play(anim.idle)
        slot0.say(t57.u7)
        slot0.play(28)
        sound(8, 8)
        wait(1000)
        tamer.say(t57.u8)
        tamer.run(-150, 921, wait=False)
        partner.run(150, 721, wait=False)
        wait(1000)
        tamer.face(slot0)
        wait(250)
        slot0.say(t57.u9)
        raw.entity_move_to(slot0, 145, 795, 5, 0)
        slot0.arrived()
        camera.to(0, 1614, speed=20)
        camera.arrived()
        raw.entity_move_to(slot0, 0, -489, 5, 0)
        slot0.arrived()
        tamer.face(slot0)
        wait(500)
        tamer.say(t57.u10)
        tamer.face(slot0)
        wait(500)
        slot0.face(tamer)
        wait(500)
        slot0.say(t57.u11)
        tamer.run(50, 250, wait=False)
        raw.entity_move_to(slot0, 50, -1640, 12, 0)
        slot0.arrived()
        tamer.arrived()
        slot0.leave()
        tamer.run(50, -480)
        tamer.say(t57.u12)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if not mansion_entrance_seen:
        mansion_entrance_seen.set()
        wait(1000)
        tamer.turn(2048)
        tamer.arrived()
        wait(500)
        tamer.turn(2560)
        tamer.arrived()
        wait(500)
        tamer.turn(1536)
        tamer.arrived()
        wait(500)
        camera.to(-997, -977, speed=30)
        camera.arrived()
        camera.to(-1035, 4000, speed=50)
        camera.arrived()
        camera.to(1222, 4000, speed=30)
        camera.arrived()
        camera.to(1066, -977, speed=50)
        camera.arrived()
        tamer.turn(2560)
        camera.on(tamer, speed=30)
        camera.arrived()
        tamer.turn(2048)
        partner.turn(2048)
        tamer.arrived()
        partner.arrived()
        tamer.say(t57.u13)
        tamer.walk(-6, -1255, camera=True)
        tamer.play(24)
        wait(750)
        tamer.say(t57.u14)
        tamer.play(anim.idle)
        wait(2000)
        tamer.face(partner)
        tamer.arrived()
        partner.face(tamer)
        partner.arrived()
        tamer.say(t57.u15)
        tamer.turn(3584)
        tamer.arrived()
        tamer.turn(3072)
        tamer.arrived()
        tamer.turn(2560)
        tamer.arrived()
        tamer.turn(2048)
        tamer.arrived()
        raw.show_textbox(t57.u16)
        return

@mansion.on_use(4)
def use4():    # section 84
    if has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit4:
        tamer.turn(1024)
        sound(8, 3)
        narrator.say(t84.u0)
        mansion_door_unlocked.s52_s55_exit4.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit4:
        tamer.turn(1024)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t84.u1)
        return
    swing_door(4)
    sound(8, 1)
    wait(500)
    tamer.walk(-2000, 1433, wait=False)
    warp(Screen.grey_lords_mansion_55, entry=1)

@mansion.on_use(5)
def use5():    # section 85
    if has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit5:
        tamer.turn(1024)
        sound(8, 3)
        narrator.say(t85.u0)
        mansion_door_unlocked.s52_s55_exit5.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit5:
        tamer.turn(1024)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t85.u1)
        return
    swing_door(5)
    sound(8, 1)
    wait(500)
    tamer.walk(-2000, -882, wait=False)
    warp(Screen.grey_lords_mansion_55, entry=2)

@mansion.on_use(2)
def use2():    # section 82
    if has(Item.MansionKey) and not mansion_door_unlocked.s52_s59:
        tamer.turn(3072)
        sound(8, 3)
        narrator.say(t82.u0)
        mansion_door_unlocked.s52_s59.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s52_s59:
        tamer.turn(3072)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t82.u1)
        return
    swing_door(2)
    sound(8, 1)
    wait(500)
    tamer.walk(2000, 1171, wait=False)
    warp(Screen.grey_lords_mansion_59, entry=0)

@mansion.on_step(7)
def step7():    # section 58
    tamer.walk(0, -2000, wait=False)
    sound(8, 1)
    warp(Screen.overdell_cemetery, entry=0)

@mansion.on_use(1)
def use1():    # section 81
    if not mansion_devimon_met:
        tamer.turn(3072)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t81.u0)
        return
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(2000, -722, wait=False)
    warp(Screen.grey_lords_mansion_60, entry=0)

@mansion.on_use(3)
def use3():    # section 83
    swing_door(3)
    sound(8, 1)
    wait(500)
    tamer.walk(1005, 3000, wait=False)
    warp(Screen.grey_lords_mansion_57, entry=2)
    return

# the section table, in the order of the original header
sections(254, 57, 84, 85, 82, 58, 81, 83)
