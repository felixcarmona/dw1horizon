# The Python view of script 112 of DG.SCN: screen 116 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_116)
morishellmon0 = trees.npc(Species.MoriShellmon, slot=0)
morishellmon1 = trees.npc(Species.MoriShellmon, slot=1)
morishellmon2 = trees.npc(Species.MoriShellmon, slot=2)
fugamon3 = trees.npc(Species.Fugamon, slot=3)
fugamon4 = trees.npc(Species.Fugamon, slot=4)
darklizardmon5 = trees.npc(Species.DarkLizardmon, slot=5)
darklizardmon6 = trees.npc(Species.DarkLizardmon, slot=6)
t10 = text.s112.sec10
t11 = text.s112.sec11
t5 = text.s112.sec5
t6 = text.s112.sec6
t7 = text.s112.sec7
t8 = text.s112.sec8
t9 = text.s112.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 11:
        spawn_item(Item.Digimushrm, at=(-1850, -650))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(550, -250))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Happymushrm, at=(-950, -3050))

@morishellmon0.on_talk
def talk():    # section 5
    recruitable(morishellmon0, line=t5.u0)

@morishellmon1.on_talk
def talk():    # section 6
    recruitable(morishellmon1, line=t6.u0)

@morishellmon2.on_talk
def talk():    # section 7
    recruitable(morishellmon2, line=t7.u0)

@fugamon3.on_talk
def talk():    # section 8
    recruitable(fugamon3, line=t8.u0)

@fugamon4.on_talk
def talk():    # section 9
    recruitable(fugamon4, line=t9.u0)

@darklizardmon5.on_talk
def talk():    # section 10
    recruitable(darklizardmon5, line=t10.u0)

@darklizardmon6.on_talk
def talk():    # section 11
    recruitable(darklizardmon6, line=t11.u0)

@trees.on_step(0)
def step0():    # section 51
    tamer.walk(2200, -2600, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_117, entry=0)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_117, entry=0)
        return step1()
    warp(Screen.misty_trees_121, entry=0)
    return step1()

@trees.on_step(1)
def step1():    # section 52
    tamer.walk(1600, 1800, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_118, entry=0)
    roll = random.roll(99)
    if roll < 49:
        warp(Screen.misty_trees_118, entry=0)
    else:
        warp(Screen.misty_trees_121, entry=0)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 51, 52)
