# The Python view of script 67 of DG.SCN: screen 70 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

savanna = screen(Screen.gear_savanna_70)
psychemon0 = savanna.npc(Species.Psychemon, slot=0)
psychemon1 = savanna.npc(Species.Psychemon, slot=1)
shimaunimon = savanna.npc(Species.ShimaUnimon, slot=2)
nisedrimogemon3 = savanna.npc(Species.NiseDrimogemon, slot=3)
nisedrimogemon4 = savanna.npc(Species.NiseDrimogemon, slot=4)
shamamon = savanna.npc(Species.Shamamon, slot=5)
t10 = text.s067.sec10
t5 = text.s067.sec5
t6 = text.s067.sec6
t7 = text.s067.sec7
t8 = text.s067.sec8
t9 = text.s067.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-950, -3450))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(1850, -2250))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-1050, -950))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.SweetNut, at=(1750, 2550))

@psychemon0.on_talk
def talk():    # section 5
    recruitable(psychemon0, line=t5.u0)

@psychemon1.on_talk
def talk():    # section 6
    recruitable(psychemon1, line=t6.u0)

@shimaunimon.on_talk
def talk():    # section 7
    recruitable(shimaunimon, line=t7.u0)

@nisedrimogemon3.on_talk
def talk():    # section 8
    recruitable(nisedrimogemon3, line=t8.u0)

@nisedrimogemon4.on_talk
def talk():    # section 9
    recruitable(nisedrimogemon4, line=t9.u0)

@shamamon.on_talk
def talk():    # section 10
    recruitable(shamamon, line=t10.u0)

@savanna.on_step(0)
def step0():    # section 51
    if clock.day >= 15 and clock.day < 30:
        tamer.walk(-2800, 1723, wait=False)
        warp(Screen.gear_savanna_75, entry=0)
    tamer.walk(-2800, 1723, wait=False)
    warp(Screen.gear_savanna_131, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 51)
