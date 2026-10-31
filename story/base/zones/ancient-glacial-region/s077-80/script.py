# The Python view of script 77 of DG.SCN: screen 80 Ancient Glacial Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

region = screen(Screen.ancient_glacial_region_80)
vermilimon0 = region.npc(Species.Vermilimon, slot=0)
yanmamon1 = region.npc(Species.Yanmamon, slot=1)
vermilimon2 = region.npc(Species.Vermilimon, slot=2)
yanmamon3 = region.npc(Species.Yanmamon, slot=3)
vermilimon4 = region.npc(Species.Vermilimon, slot=4)
vermilimon5 = region.npc(Species.Vermilimon, slot=5)
t10 = text.s077.sec10
t5 = text.s077.sec5
t6 = text.s077.sec6
t7 = text.s077.sec7
t8 = text.s077.sec8
t9 = text.s077.sec9

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-1950, -3950))
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(550, -1150))
    roll = random.roll(99)
    if roll <= 13:
        spawn_item(Item.Digimushrm, at=(-2350, -250))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.RedBerry, at=(-550, 3250))

@vermilimon0.on_talk
def talk():    # section 5
    recruitable(vermilimon0, line=t5.u0)

@yanmamon1.on_talk
def talk():    # section 6
    recruitable(yanmamon1, line=t6.u0)

@vermilimon2.on_talk
def talk():    # section 7
    recruitable(vermilimon2, line=t7.u0)

@yanmamon3.on_talk
def talk():    # section 8
    recruitable(yanmamon3, line=t8.u0)

@vermilimon4.on_talk
def talk():    # section 9
    recruitable(vermilimon4, line=t9.u0, joins=Species.Vermilimon)

@vermilimon5.on_talk
def talk():    # section 10
    recruitable(vermilimon5, line=t10.u0, joins=Species.Vermilimon)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
