# The Python view of script 56 of DG.SCN: screen 57 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_57)
t53 = text.s056.sec53
t81 = text.s056.sec81

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_use(1)
def use1():    # section 81
    if has(Item.MansionKey) and not mansion_door_unlocked.s57_s58:
        tamer.turn(3138)
        sound(8, 3)
        narrator.say(t81.u0)
        mansion_door_unlocked.s57_s58.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s57_s58:
        tamer.turn(3138)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t81.u1)
        return
    swing_door(3)
    sound(8, 1)
    wait(500)
    tamer.walk(700, 50, wait=False)
    warp(Screen.grey_lords_mansion_58, entry=0)

@mansion.on_use(2)
def use2():    # section 82
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(-1400, -600, wait=False)
    warp(Screen.grey_lords_mansion_56, entry=0)

@mansion.on_use(3)
def use3():    # section 83
    swing_door(2)
    sound(8, 1)
    wait(500)
    tamer.walk(-276, -2000, wait=False)
    warp(Screen.grey_lords_mansion_52, entry=3)

@mansion.on_step(2)
def step2():    # section 53
    tamer.play(18)
    partner.play(43)
    damage_percent.set(30)
    raw.deal_damage(damage_percent)
    wait(1000)
    partner.play(44)
    wait(1000)
    tamer.say(t53.u0)
    call(Routine.loop_once, arg=253)
    return

# the section table, in the order of the original header
sections(254, 81, 82, 83, 53)
