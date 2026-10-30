# The Python view of script 54 of DG.SCN: screen 55 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_55)
myotismon = mansion.npc(Species.Myotismon177, slot=0)
t254 = text.s054.sec254
t5 = text.s054.sec5
t60 = text.s054.sec60
t81 = text.s054.sec81
t82 = text.s054.sec82
t83 = text.s054.sec83

@mansion.on_enter
def enter():    # section 254
    if mansion_key_found:
        objects[14].show()
    if myotismon_missing and not myotismon_absence_seen.mansion:
        wait(1000)
        tamer.turn(1024)
        wait(250)
        camera.to(234, 211, speed=30)
        camera.arrived()
        tamer.say(t254.u0)
        myotismon_absence_seen.mansion.set()
        camera.on(tamer, speed=10)
        camera.arrived()

@mansion.on_use(1)
def use1():    # section 81
    if not mansion_key_found:
        tamer.say(t81.u0)
        tamer.play(12)
        wait(1000)
        objects[14].show()
        give(Item.MansionKey)
        tamer.say(t81.u1)
        narrator.say(t81.u2)
        if engine.item_did_not_fit:
            tamer.say(t81.u3)
            engine.picker_mode.clear()
            call(Routine.choose_item)
            take_picked(all=True)
            give(Item.MansionKey)
        mansion_key_found.set()
    else:
        return

@mansion.on_use(2)
def use2():    # section 82
    if has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit4:
        tamer.turn(2954)
        sound(8, 3)
        narrator.say(t82.u0)
        mansion_door_unlocked.s52_s55_exit4.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit4:
        tamer.turn(2954)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t82.u1)
        return
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(1600, 1674, wait=False)
    warp(Screen.grey_lords_mansion_52, entry=4)

@mansion.on_use(4)
def use4():    # section 84
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(-866, 3000, wait=False)
    warp(Screen.grey_lords_mansion_54, entry=1)

@mansion.on_use(3)
def use3():    # section 83
    if has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit5:
        tamer.turn(2954)
        sound(8, 3)
        narrator.say(t83.u0)
        mansion_door_unlocked.s52_s55_exit5.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s52_s55_exit5:
        tamer.turn(2954)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t83.u1)
        return
    swing_door(2)
    sound(8, 1)
    wait(500)
    tamer.walk(1600, -1546, wait=False)
    warp(Screen.grey_lords_mansion_52, entry=5)

@mansion.on_step(9)
def step9():    # section 60
    spawn(Species.Devimon, slot=0)
    tamer.turn(906)
    partner.run(775, -69)
    partner.turn(906)
    tamer.say(t60.u0)
    myotismon.say(t60.u1)
    myotismon.face(tamer)
    myotismon.say(t60.u2)
    tamer.say(t60.u3)
    myotismon.say(t60.u4)
    tamer.say(t60.u5)
    myotismon.say(t60.u6)
    tamer.face(myotismon)
    tamer.say(t60.u7)
    myotismon.say(t60.u8)
    tamer.say(t60.u9)
    myotismon.say(t60.u10)
    tamer.say(t60.u11)
    myotismon.say(t60.u12)
    tamer.say(t60.u13)
    myotismon.say(t60.u14)
    tamer.say(t60.u15)
    myotismon.say(t60.u16)
    tamer.say(t60.u17)
    myotismon.say(t60.u18)
    tamer.say(t60.u19)
    return

@myotismon.on_talk
def talk():    # section 5
    if recruited(Species.SkullGreymon):
        say(t5.u0)
        return
    if recruited(Species.Myotismon):
        say(t5.u1)
        tamer.say(t5.u2)
        return
    if recruited(Species.Greymon):
        say(t5.u3)
        say(t5.u4)
        tamer.say(t5.u5)
        recruit(Species.Myotismon)
    else:
        say(t5.u6)
        return
    return

# the section table, in the order of the original header
sections(254, 81, 82, 84, 83, 60, 5)
