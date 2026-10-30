# The Python view of script 74 of DG.SCN: screen 77 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

savanna = screen(Screen.gear_savanna_77)
shimaunimon = savanna.npc(Species.ShimaUnimon, slot=0)
shamamon1 = savanna.npc(Species.Shamamon, slot=1)
shamamon2 = savanna.npc(Species.Shamamon, slot=2)
nisedrimogemon = savanna.npc(Species.NiseDrimogemon, slot=3)
shamamon4 = savanna.npc(Species.Shamamon, slot=4)
shamamon5 = savanna.npc(Species.Shamamon, slot=5)
t10 = text.s074.sec10
t5 = text.s074.sec5
t6 = text.s074.sec6
t7 = text.s074.sec7
t8 = text.s074.sec8
t9 = text.s074.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-2250, -2750))
    roll = random.roll(99)
    if roll <= 10:
        spawn_item(Item.Digimushrm, at=(1250, -850))

@shimaunimon.on_talk
def talk():    # section 5
    recruitable(shimaunimon, line=t5.u0)

@shamamon1.on_talk
def talk():    # section 6
    recruitable(shamamon1, line=t6.u0)

@shamamon2.on_talk
def talk():    # section 7
    recruitable(shamamon2, line=t7.u0)

@nisedrimogemon.on_talk
def talk():    # section 8
    recruitable(nisedrimogemon, line=t8.u0, joins=Species.ShimaUnimon)

@shamamon4.on_talk
def talk():    # section 9
    recruitable(shamamon4, line=t9.u0)

@shamamon5.on_talk
def talk():    # section 10
    recruitable(shamamon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
