# The Python view of script 19 of DG.SCN: screen 18 Path Thru Mt. Panorama.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

panorama = screen(Screen.path_thru_mt_panorama_18)
goblimon0 = panorama.npc(Species.Goblimon, slot=0)
goblimon1 = panorama.npc(Species.Goblimon, slot=1)
aruraumon2 = panorama.npc(Species.Aruraumon, slot=2)
aruraumon3 = panorama.npc(Species.Aruraumon, slot=3)
slot4 = entity(9)
slot5 = entity(10)
gotsumon6 = panorama.npc(Species.Gotsumon, slot=6)
gotsumon7 = panorama.npc(Species.Gotsumon, slot=7)
t10 = text.s019.sec10
t11 = text.s019.sec11
t12 = text.s019.sec12
t5 = text.s019.sec5
t6 = text.s019.sec6
t7 = text.s019.sec7
t8 = text.s019.sec8
t9 = text.s019.sec9

@panorama.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-1250, 3050))
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(1050, -2250))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.BigBerry, at=(750, -450))
    native_forest_rockslide_cleared.set()
    native_forest_rockslide_cleared_seen.set()

@goblimon0.on_talk
def talk():    # section 5
    recruitable(goblimon0, line=t5.u0)

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@aruraumon2.on_talk
def talk():    # section 7
    recruitable(aruraumon2, line=t7.u0)

@aruraumon3.on_talk
def talk():    # section 8
    recruitable(aruraumon3, line=t8.u0)

@slot4.on_talk
def talk():    # section 9
    recruitable(slot4, line=t9.u0, joins=Species.Goblimon)

@slot5.on_talk
def talk():    # section 10
    recruitable(slot5, line=t10.u0, joins=Species.Goblimon)

@gotsumon6.on_talk
def talk():    # section 11
    recruitable(gotsumon6, line=t11.u0)

@gotsumon7.on_talk
def talk():    # section 12
    recruitable(gotsumon7, line=t12.u0)

@panorama.on_step(0)
def step0():    # section 51
    warp(Screen.path_thru_mt_panorama_20, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 12, 51)
