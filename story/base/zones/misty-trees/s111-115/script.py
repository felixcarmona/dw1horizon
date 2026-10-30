# The Python view of script 111 of DG.SCN: screen 115 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_115)
fugamon0 = trees.npc(Species.Fugamon, slot=0)
fugamon1 = trees.npc(Species.Fugamon, slot=1)
morishellmon = trees.npc(Species.MoriShellmon, slot=2)
darklizardmon3 = trees.npc(Species.DarkLizardmon, slot=3)
darklizardmon4 = trees.npc(Species.DarkLizardmon, slot=4)
tsukaimon = trees.npc(Species.Tsukaimon, slot=5)
t10 = text.s111.sec10
t5 = text.s111.sec5
t6 = text.s111.sec6
t7 = text.s111.sec7
t8 = text.s111.sec8
t9 = text.s111.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(50, 1050))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-1550, -2850))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(-1750, 850))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Happymushrm, at=(-50, -2450))
    misty_trees_visited.set()

@fugamon0.on_talk
def talk():    # section 5
    recruitable(fugamon0, line=t5.u0)

@fugamon1.on_talk
def talk():    # section 6
    recruitable(fugamon1, line=t6.u0)

@morishellmon.on_talk
def talk():    # section 7
    recruitable(morishellmon, line=t7.u0)

@darklizardmon3.on_talk
def talk():    # section 8
    recruitable(darklizardmon3, line=t8.u0)

@darklizardmon4.on_talk
def talk():    # section 9
    recruitable(darklizardmon4, line=t9.u0)

@tsukaimon.on_talk
def talk():    # section 10
    recruitable(tsukaimon, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
