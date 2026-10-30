# The Python view of script 34 of DG.SCN: screen 34 Overdell.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

overdell = screen(Screen.overdell)
darklizardmon0 = overdell.npc(Species.DarkLizardmon, slot=0)
darklizardmon1 = overdell.npc(Species.DarkLizardmon, slot=1)
darklizardmon2 = overdell.npc(Species.DarkLizardmon, slot=2)
darklizardmon3 = overdell.npc(Species.DarkLizardmon, slot=3)
darklizardmon4 = overdell.npc(Species.DarkLizardmon, slot=4)
darklizardmon5 = overdell.npc(Species.DarkLizardmon, slot=5)
tsukaimon6 = overdell.npc(Species.Tsukaimon, slot=6)
tsukaimon7 = overdell.npc(Species.Tsukaimon, slot=7)
t10 = text.s034.sec10
t11 = text.s034.sec11
t12 = text.s034.sec12
t5 = text.s034.sec5
t6 = text.s034.sec6
t7 = text.s034.sec7
t8 = text.s034.sec8
t9 = text.s034.sec9

@overdell.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-2850, 1850))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(950, -2850))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.Deluxmushrm, at=(1050, -150))

@darklizardmon0.on_talk
def talk():    # section 5
    recruitable(darklizardmon0, line=t5.u0)

@darklizardmon1.on_talk
def talk():    # section 6
    recruitable(darklizardmon1, line=t6.u0)

@darklizardmon2.on_talk
def talk():    # section 7
    recruitable(darklizardmon2, line=t7.u0)

@darklizardmon3.on_talk
def talk():    # section 8
    recruitable(darklizardmon3, line=t8.u0)

@darklizardmon4.on_talk
def talk():    # section 9
    recruitable(darklizardmon4, line=t9.u0)

@darklizardmon5.on_talk
def talk():    # section 10
    recruitable(darklizardmon5, line=t10.u0)

@tsukaimon6.on_talk
def talk():    # section 11
    recruitable(tsukaimon6, line=t11.u0)

@tsukaimon7.on_talk
def talk():    # section 12
    recruitable(tsukaimon7, line=t12.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 12)
