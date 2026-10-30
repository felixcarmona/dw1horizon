# The Python view of script 109 of DG.SCN: screen 113 Leomon Ancestor's Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

cave = screen(Screen.leomon_ancestors_cave_113)
nanimon = cave.npc(Species.Nanimon171, slot=0)
t5 = text.s109.sec5
t51 = text.s109.sec51
t52 = text.s109.sec52

@cave.on_enter
def enter():    # section 254
    if leomon_stone_taken:
        objects[2].show()

@cave.on_step(0)
def step0():    # section 51
    if not leomon_cave_first_seen:
        tamer.turn(1900)
        tamer.arrived()
        tamer.say(t51.u0)
        camera.to(-400, 4000, speed=50)
        camera.arrived()
        wait(2000)
        camera.on(tamer, speed=20)
        camera.arrived()
        leomon_cave_first_seen.set()
        return

@cave.on_step(1)
def step1():    # section 52
    if not leomon_stone_taken:
        tamer.turn(1900)
        tamer.arrived()
        tamer.say(t52.u0)
        tamer.walk(-477, 2801, camera=True)
        tamer.turn(1900)
        wait(500)
        tamer.play(25)
        wait(500)
        sound(8, 7)
        objects[2].show()
        wait(500)
        tamer.say(t52.u1)
        tamer.play(16)
        wait(750)
        tamer.say(t52.u2)
        tamer.play(anim.idle)
        tamer.say(t52.u3)
        give(Item.Leomonstone)
        if engine.item_did_not_fit:
            tamer.say(t52.u4)
            engine.picker_mode.clear()
            call(Routine.choose_item)
            take_picked(all=True)
            give(Item.Leomonstone)
        sound(0, 7)
        narrator.say(t52.u5)
        leomon_stone_taken.set()
        return

@nanimon.on_talk
def talk():    # section 5
    wait(500)
    play(28)
    wait(500)
    tamer.say(t5.u0)
    say(t5.u1)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    turn(1276)
    wait(250)
    turn(2300)
    wait(250)
    turn(3324)
    wait(250)
    turn(252)
    wait(250)
    run(-1412, 1251)
    leave()
    if key_chains == 0:
        objects[3].hide()
        tamer.run(-1878, 2900)
        tamer.play(12)
        wait(500)
        objects[3].show()
        sound(0, 7)
        narrator.say(t5.u2)
        sound(0, 7)
        raw.set_inventory_size(20)
        inventory_expanded.to_20.set()
    if key_chains == 4:
        objects[4].hide()
        tamer.run(-1878, 2900)
        tamer.play(12)
        wait(500)
        objects[4].show()
        sound(0, 7)
        narrator.say(t5.u3)
        inventory_expanded.to_30.set()
        raw.set_inventory_size(30)
        recruit(Species.Nanimon)
        engine.prosperity.add(1)
    key_chains.add(1)
    key_chain_found.leomon_cave.set()
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5)
