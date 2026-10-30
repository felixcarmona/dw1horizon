# The Python view of script 63 of DG.SCN: screen 66 Mansion Basement.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

basement = screen(Screen.mansion_basement)
myotismon = basement.npc(Species.Myotismon177, slot=0)
machinedramon = basement.npc(Species.Machinedramon, slot=1)
analogman = basement.npc(Species.Analogman, slot=2)
slot3 = basement.npc(None, slot=3)    # the .MAP has Soulmon here; the script spawns what stands here
t254 = text.s063.sec254
t5 = text.s063.sec5
t60 = text.s063.sec60

@basement.on_enter
def enter():    # section 254
    if not myotismon_met or not myotismon_freed:
        myotismon.play(28)
    if not myotismon_joined_city and myotismon_missing:
        wait(1000)
        tamer.turn(2048)
        wait(250)
        tamer.say(t254.u0)
        myotismon_absence_seen.basement.set()

@myotismon.on_talk(scene=True)
def talk():    # section 5
    tamer.run(-253, -1358, camera=True)
    tamer.face(myotismon)
    play(29)
    wait(250)
    if has(Item.Steak):
        take(Item.Steak)
        say(t5.u17)
        play(30)
        wait(2000)
        play(anim.idle)
        face(tamer)
        say(t5.u18)
        tamer.say(t5.u19)
        say(t5.u20)
        tamer.say(t5.u21)
        say(t5.u22)
        myotismon_freed.set()
        raw.entity_move_to(myotismon, -29, -2765, 30, 0)
        wait(1500)
        tamer.walk(-29, -2765, wait=False)
        arrived()
        leave()
        wait(500)
        partner.walk(-29, -2765, wait=False)
        wait(500)
        warp(Screen.grey_lords_mansion_224, entry=0, then=60)
        return
    if myotismon_met:
        say(t5.u0)
    else:
        myotismon_met.set()
        tamer.say(t5.u1)
        say(t5.u2)
        tamer.say(t5.u3)
        say(t5.u4)
        tamer.say(t5.u5)
        say(t5.u6)
        if has(Item.Meat) or has(Item.GiantMeat) or has(Item.Sirloin):
            tamer.say(t5.u7)
            say(t5.u8)
            tamer.say(t5.u9)
        else:
            tamer.say(t5.u10)
        say(t5.u11)
        give(Item.FrigKey)
        tamer.say(t5.u12)
        if engine.item_did_not_fit:
            tamer.say(t5.u13)
            engine.picker_mode.clear()
            call(Routine.choose_item)
            take_picked(all=True)
            give(Item.FrigKey)
        narrator.say(t5.u14)
        say(t5.u15)
    tamer.say(t5.u16)
    play(28)
    return

@basement.on_step(9)
def step9():    # section 60
    wait(2000)
    camera.to(-1455, 1463, speed=20)
    tamer.play(15)
    wait(1000)
    tamer.say(t60.u0)
    analogman.say(t60.u1)
    tamer.say(t60.u2)
    analogman.arrived()
    analogman.leave()
    wait(1000)
    tamer.say(t60.u3)
    machinedramon.play(28)
    wait(2000)
    wait(2000)
    fight(machinedramon, escape=False)
    machinedramon.walk(-100, 800)
    machinedramon.play(43)
    wait(2000)
    tamer.say(t60.u4)
    tamer.face(machinedramon)
    machinedramon.arrived()
    tamer.arrived()
    machinedramon.leave()
    tamer.say(t60.u5)
    load(Species.Soulmon)
    spawn(Species.Soulmon, slot=3)
    slot3.say(t60.u6)
    slot3.face(tamer)
    wait(1000)
    slot3.say(t60.u7)
    recruit(Species.Koromon)
    back_dimension_portal.set(0)
    days_since_passed_out.set(0)
    recruit(Species.Yuramon)
    slot3.walk_away(-40, -2800, looks=3)
    slot3.leave()
    glances.set(0)
    tamer.play(16)
    wait(2000)
    tamer.say(t60.u8)
    wait(1000)
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if not recruited(Species.Birdramon):
            if recruited(Species.Vegiemon):
                warp(Screen.file_city_170, entry=0)
            if recruited(Species.Palmon):
                warp(Screen.file_city_169, entry=0)
            warp(Screen.file_city_168, entry=0)
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=0)
        warp(Screen.file_city_171, entry=0)
    if not recruited(Species.Birdramon):
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_176, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_175, entry=0)
        warp(Screen.file_city_174, entry=0)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=0)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=0)
    warp(Screen.file_city_177, entry=0)

# the section table, in the order of the original header
sections(254, 5, 60)
