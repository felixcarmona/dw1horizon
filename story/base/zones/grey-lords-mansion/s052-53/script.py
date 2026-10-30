# The Python view of script 52 of DG.SCN: screen 53 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_53)
t81 = text.s052.sec81
t82 = text.s052.sec82
t83 = text.s052.sec83

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_use(2)
def use2():    # section 82
    if has(Item.MansionKey) and not mansion_door_unlocked.s53_s64:
        tamer.turn(3072)
        sound(8, 3)
        narrator.say(t82.u0)
        mansion_door_unlocked.s53_s64.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s53_s64:
        tamer.turn(3072)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t82.u1)
        return
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(2000, 2500, wait=False)
    warp(Screen.grey_lords_mansion_64, entry=0)

@mansion.on_use(3)
def use3():    # section 83
    if not mansion_door_unlocked.s53_s63:
        tamer.turn(1024)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t83.u0)
        return
    tamer.walk(-2000, 554, wait=False)
    swing_door(2)
    sound(8, 1)
    wait(500)
    warp(Screen.grey_lords_mansion_63, entry=0)

@mansion.on_use(1)
def use1():    # section 81
    if has(Item.MansionKey) and not mansion_door_unlocked.s53_s232:
        tamer.turn(3072)
        sound(8, 3)
        narrator.say(t81.u0)
        mansion_door_unlocked.s53_s232.set()
    elif not has(Item.MansionKey) and not mansion_door_unlocked.s53_s232:
        tamer.turn(3072)
        sound(8, 2)
        wait(250)
        sound(8, 2)
        narrator.say(t81.u1)
        return
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(2000, 550, wait=False)
    warp(Screen.grey_lords_mansion_232, entry=0)

def sec81_dup4():    # shared code (the disc's label sec81_dup4)
    return

# the section table, in the order of the original header
sections(254, 82, 83, 81, (81, sec81_dup4))
