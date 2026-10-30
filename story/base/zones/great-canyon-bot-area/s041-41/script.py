# The Python view of script 41 of DG.SCN: screen 41 Great Canyon Bot. Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.great_canyon_bot_area_41)
muchomon0 = area.npc(Species.Muchomon, slot=0)
muchomon1 = area.npc(Species.Muchomon, slot=1)
weedmon2 = area.npc(Species.Weedmon, slot=2)
weedmon3 = area.npc(Species.Weedmon, slot=3)
weedmon4 = area.npc(Species.Weedmon, slot=4)
goblimon = area.npc(Species.Goblimon, slot=5)
t10 = text.s041.sec10
t5 = text.s041.sec5
t6 = text.s041.sec6
t7 = text.s041.sec7
t8 = text.s041.sec8
t81 = text.s041.sec81
t9 = text.s041.sec9

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(1950, 50))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-1250, 1650))

@muchomon0.on_talk
def talk():    # section 5
    recruitable(muchomon0, line=t5.u0)

@muchomon1.on_talk
def talk():    # section 6
    recruitable(muchomon1, line=t6.u0)

@weedmon2.on_talk
def talk():    # section 7
    recruitable(weedmon2, line=t7.u0)

@weedmon3.on_talk
def talk():    # section 8
    recruitable(weedmon3, line=t8.u0)

@weedmon4.on_talk
def talk():    # section 9
    recruitable(weedmon4, line=t9.u0)

@goblimon.on_talk
def talk():    # section 10
    recruitable(goblimon, line=t10.u0)

@area.on_use(1)
def use1():    # section 81
    tamer.turn(2128)
    wait(250)
    narrator.say(t81.u0)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            if not canyon_elevator_unjammed:
                tamer.play(16)
                wait(750)
                tamer.say(t81.u1)
                tamer.play(anim.idle)
                tamer.turn(2297)
                wait(500)
                tamer.turn(1785)
                wait(500)
                tamer.turn(2297)
                raw.show_textbox(t81.u2)
                tamer.play(25)
                wait(1000)
                narrator.say(t81.u3)
                tamer.say(t81.u4)
                canyon_elevator_unjammed.set()
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
            sound(8, 5)
            warp(Screen.great_canyon_129, entry=0, then=52)
            return
        case "b":
            hide_hud()
            if not canyon_elevator_unjammed:
                tamer.play(16)
                wait(750)
                tamer.say(t81.u5)
                tamer.play(anim.idle)
                tamer.turn(2297)
                wait(500)
                tamer.turn(1785)
                wait(500)
                tamer.turn(2297)
                raw.show_textbox(t81.u6)
                narrator.say(t81.u7)
                tamer.say(t81.u8)
                canyon_elevator_unjammed.set()
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
            sound(8, 5)
            warp(Screen.great_canyon_top_area_38, entry=2, then=55)
            return

@area.on_step(2)
def step2():    # section 53
    sound(8, 5)
    canyon_elevator_ridden.set()
    ogre_fortress_elevator_ridden.clear()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81, 53)
