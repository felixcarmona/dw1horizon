# The Python view of script 38 of DG.SCN: screen 38 Great Canyon Top Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.great_canyon_top_area_38)
weedmon = area.npc(Species.Weedmon, slot=0)
sandyanmamon1 = area.npc(Species.SandYanmamon, slot=1)
sandyanmamon2 = area.npc(Species.SandYanmamon, slot=2)
gotsumon3 = area.npc(Species.Gotsumon, slot=3)
gotsumon4 = area.npc(Species.Gotsumon, slot=4)
t5 = text.s038.sec5
t6 = text.s038.sec6
t7 = text.s038.sec7
t8 = text.s038.sec8
t81 = text.s038.sec81
t82 = text.s038.sec82
t9 = text.s038.sec9

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-50, -1450))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-3050, 1850))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Pricklypear, at=(-2950, 4050))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.Deluxmushrm, at=(1950, 3350))

@weedmon.on_talk
def talk():    # section 5
    recruitable(weedmon, line=t5.u0)

@sandyanmamon1.on_talk
def talk():    # section 6
    recruitable(sandyanmamon1, line=t6.u0)

@sandyanmamon2.on_talk
def talk():    # section 7
    recruitable(sandyanmamon2, line=t7.u0)

@gotsumon3.on_talk
def talk():    # section 8
    recruitable(gotsumon3, line=t8.u0)

@gotsumon4.on_talk
def talk():    # section 9
    recruitable(gotsumon4, line=t9.u0)

@area.on_use(1)
def use1():    # section 81
    narrator.say(t81.u0)

@area.on_use(2)
def use2():    # section 82
    tamer.turn(2048)
    wait(250)
    narrator.say(t82.u0)
    match choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "a":
            sound(8, 4)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            sound(8, 5)
            warp(Screen.great_canyon_129, entry=0, then=52)
            return
        case "b":
            hide_hud()
            if not canyon_elevator_unjammed:
                tamer.say(t82.u1)
                return
            sound(8, 4)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            swing_door(0)
            wait(50)
            swing_door(1)
            wait(50)
            sound(8, 5)
            warp(Screen.great_canyon_bot_area_41, entry=2, then=53)
            return

@area.on_step(4)
def step4():    # section 55
    sound(8, 5)

@area.on_step(0)
def step0():    # section 51
    tamer.walk(2100, -4000, wait=False)
    if canyon_cave_in.collapsed:
        warp(Screen.great_canyon_128, entry=1)
    warp(Screen.great_canyon_top_area_43, entry=1)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 81, 82, 55, 51)
