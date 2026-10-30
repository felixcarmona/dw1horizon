# The Python view of script 55 of DG.SCN: screen 56 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_56)
soulmon0 = mansion.npc(Species.Soulmon, slot=0)
soulmon1 = mansion.npc(Species.Soulmon, slot=1)
soulmon2 = mansion.npc(Species.Soulmon, slot=2)
t5 = text.s055.sec5
t6 = text.s055.sec6
t7 = text.s055.sec7
t83 = text.s055.sec83

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.Sirloin, at=(500, 567), opened=trigger(653))
    mansion_fridge_open.clear()

@soulmon0.on_talk
def talk():    # section 5
    recruitable(soulmon0, line=t5.u0)

@soulmon1.on_talk
def talk():    # section 6
    recruitable(soulmon1, line=t6.u0)

@soulmon2.on_talk
def talk():    # section 7
    recruitable(soulmon2, line=t7.u0)

@mansion.on_use(3)
def use3():    # section 83
    tamer.turn(1024)
    wait(250)
    if mansion_fridge_memo_found:
        if not mansion_fridge_open:
            swing_door(2)
            swing_door(3)
        wait(1000)
        tamer.say(t83.u0)
        narrator.say(t83.u1)
        mansion_fridge_open.set()
        return
    if has(Item.FrigKey) and not mansion_fridge_memo_found:
        mansion_fridge_open.set()
        sound(8, 3)
        narrator.say(t83.u2)
        swing_door(2)
        swing_door(3)
        wait(3000)
        take(Item.FrigKey)
        tamer.play(24)
        wait(750)
        tamer.say(t83.u3)
        tamer.play(anim.idle)
        tamer.say(t83.u4)
        narrator.say(t83.u5)
        tamer.say(t83.u6)
        mansion_fridge_memo_found.set()
        return
    if not has(Item.FrigKey) and not mansion_fridge_memo_found:
        tamer.say(t83.u7)
        tamer.say(t83.u8)
        return

@mansion.on_use(1)
def use1():    # section 81
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(81, -1600, wait=False)
    warp(Screen.grey_lords_mansion_54, entry=0)

@mansion.on_use(2)
def use2():    # section 82
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(-117, 1200, wait=False)
    warp(Screen.grey_lords_mansion_57, entry=1)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 83, 81, 82)
