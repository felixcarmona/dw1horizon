# The Python view of script 37 of DG.SCN: screen 37 Great Canyon Top Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.great_canyon_top_area_37)
goblimon0 = area.npc(Species.Goblimon, slot=0)
goblimon1 = area.npc(Species.Goblimon, slot=1)
goblimon2 = area.npc(Species.Goblimon, slot=2)
weedmon3 = area.npc(Species.Weedmon, slot=3)
weedmon4 = area.npc(Species.Weedmon, slot=4)
weedmon5 = area.npc(Species.Weedmon, slot=5)
t10 = text.s037.sec10
t5 = text.s037.sec5
t6 = text.s037.sec6
t7 = text.s037.sec7
t8 = text.s037.sec8
t81 = text.s037.sec81
t9 = text.s037.sec9

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-1450, 4050))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-3050, 1850))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.Happymushrm, at=(-3850, 3950))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.Deluxmushrm, at=(-350, 350))
    if not canyon_elevator_ridden:
        objects[2].hide()
        return
    objects[2].show()

@goblimon0.on_talk
def talk():    # section 5
    recruitable(goblimon0, line=t5.u0)

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@goblimon2.on_talk
def talk():    # section 7
    recruitable(goblimon2, line=t7.u0)

@weedmon3.on_talk
def talk():    # section 8
    recruitable(weedmon3, line=t8.u0)

@weedmon4.on_talk
def talk():    # section 9
    recruitable(weedmon4, line=t9.u0)

@weedmon5.on_talk
def talk():    # section 10
    recruitable(weedmon5, line=t10.u0)

@area.on_use(1)
def use1():    # section 81
    tamer.turn(1844)
    narrator.say(t81.u0)
    if ask(yes=t81.m0.o0, no=t81.m0.o1):
        if ogre_fortress_elevator_working:
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
            if back_dimension_portal == 3:
                warp(Screen.back_dimension_226, entry=0, then=60)
            warp(Screen.ogre_fortress_48, entry=1, then=54)
            return
        wait(1000)
        tamer.say(t81.u1)
        return

@area.on_step(2)
def step2():    # section 53
    tamer.turn(3892)
    sound(8, 5)
    canyon_elevator_ridden.set()
    ogre_fortress_elevator_ridden.clear()

@area.on_step(0)
def step0():    # section 51
    tamer.walk(4173, 2349, wait=False)
    if not canyon_elevator_ridden:
        warp(Screen.great_canyon_127, entry=0)
        return
    warp(Screen.great_canyon_bridge, entry=0)

@area.on_step(1)
def step1():    # section 52
    tamer.walk(-517, -4524, wait=False)
    if canyon_cave_in.collapsed:
        warp(Screen.great_canyon_128, entry=2)
    warp(Screen.great_canyon_top_area_43, entry=2)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81, 53, 51, 52)
