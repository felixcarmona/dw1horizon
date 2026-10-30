# The Python view of script 72 of DG.SCN: screen 75 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

savanna = screen(Screen.gear_savanna_75)
psychemon2 = savanna.npc(Species.Psychemon, slot=2)
psychemon3 = savanna.npc(Species.Psychemon, slot=3)
shamamon4 = savanna.npc(Species.Shamamon, slot=4)
shamamon5 = savanna.npc(Species.Shamamon, slot=5)
t10 = text.s072.sec10
t7 = text.s072.sec7
t8 = text.s072.sec8
t9 = text.s072.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(-50, -2050))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-2450, -1850))

@psychemon2.on_talk
def talk():    # section 7
    recruitable(psychemon2, line=t7.u0)

@psychemon3.on_talk
def talk():    # section 8
    recruitable(psychemon3, line=t8.u0)

@shamamon4.on_talk
def talk():    # section 9
    recruitable(shamamon4, line=t9.u0)

@shamamon5.on_talk
def talk():    # section 10
    recruitable(shamamon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 7, 8, 9, 10)
