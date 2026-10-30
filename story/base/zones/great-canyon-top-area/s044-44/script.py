# The Python view of script 44 of DG.SCN: screen 44 Great Canyon Top Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.great_canyon_top_area_44)
gotsumon = area.npc(Species.Gotsumon, slot=0)
weedmon = area.npc(Species.Weedmon, slot=1)
gururumon2 = area.npc(Species.Gururumon, slot=2)
gururumon3 = area.npc(Species.Gururumon, slot=3)
t5 = text.s044.sec5
t6 = text.s044.sec6
t7 = text.s044.sec7
t8 = text.s044.sec8

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-2050, 1850))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-2250, -4350))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Pricklypear, at=(-1450, -1750))

@gotsumon.on_talk
def talk():    # section 5
    recruitable(gotsumon, line=t5.u0)

@weedmon.on_talk
def talk():    # section 6
    recruitable(weedmon, line=t6.u0)

@gururumon2.on_talk
def talk():    # section 7
    recruitable(gururumon2, line=t7.u0)

@gururumon3.on_talk
def talk():    # section 8
    recruitable(gururumon3, line=t8.u0)

@area.on_step(0)
def step0():    # section 51
    if not invisible_bridge_crossed:
        return
    tamer.walk(10000, -2800, wait=False)
    warp(Screen.great_canyon_entrance, entry=1)
    return step1()

@area.on_step(1)
def step1():    # section 52
    tamer.walk(-1400, 5000, wait=False)
    if canyon_cave_in.collapsed:
        warp(Screen.great_canyon_128, entry=0)
    warp(Screen.great_canyon_top_area_43, entry=0)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51, 52)
