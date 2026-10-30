# The Python view of script 114 of DG.SCN: screen 118 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_118)
goblimon = trees.npc(Species.Goblimon, slot=0)
fugamon = trees.npc(Species.Fugamon, slot=1)
morishellmon = trees.npc(Species.MoriShellmon, slot=2)
saberdramon3 = trees.npc(Species.Saberdramon, slot=3)
saberdramon4 = trees.npc(Species.Saberdramon, slot=4)
t5 = text.s114.sec5
t6 = text.s114.sec6
t7 = text.s114.sec7
t8 = text.s114.sec8
t9 = text.s114.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(550, -2150))
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-450, -850))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-3550, 4350))

@goblimon.on_talk
def talk():    # section 5
    recruitable(goblimon, line=t5.u0)

@fugamon.on_talk
def talk():    # section 6
    recruitable(fugamon, line=t6.u0)

@morishellmon.on_talk
def talk():    # section 7
    recruitable(morishellmon, line=t7.u0)

@saberdramon3.on_talk
def talk():    # section 8
    recruitable(saberdramon3, line=t8.u0)

@saberdramon4.on_talk
def talk():    # section 9
    recruitable(saberdramon4, line=t9.u0)

@trees.on_step(0)
def step0():    # section 51
    tamer.walk(60, -3200, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_116, entry=2)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_116, entry=2)
        return step1()
    warp(Screen.misty_trees_121, entry=1)
    return step1()

@trees.on_step(1)
def step1():    # section 52
    tamer.walk(70, 5200, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_119, entry=0)
    misty_trees_maze_steps.add(1)
    if misty_trees_maze_steps == 10:
        misty_trees_maze_steps.set(0)
        warp(Screen.misty_trees_119, entry=0)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_118, entry=0)
    else:
        warp(Screen.misty_trees_116, entry=0)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 51, 52)
