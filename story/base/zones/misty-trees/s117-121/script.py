# The Python view of script 117 of DG.SCN: screen 121 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_121)
fugamon0 = trees.npc(Species.Fugamon, slot=0)
fugamon1 = trees.npc(Species.Fugamon, slot=1)
fugamon2 = trees.npc(Species.Fugamon, slot=2)
goblimon3 = trees.npc(Species.Goblimon, slot=3)
goblimon4 = trees.npc(Species.Goblimon, slot=4)
fugamon5 = trees.npc(Species.Fugamon, slot=5)
tsukaimon6 = trees.npc(Species.Tsukaimon, slot=6)
tsukaimon7 = trees.npc(Species.Tsukaimon, slot=7)
t10 = text.s117.sec10
t11 = text.s117.sec11
t12 = text.s117.sec12
t5 = text.s117.sec5
t6 = text.s117.sec6
t7 = text.s117.sec7
t8 = text.s117.sec8
t9 = text.s117.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(-1450, 3050))
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(550, -50))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Digimushrm, at=(-250, 4550))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.Digipine, at=(-950, 450))
    misty_trees_visited.set()

@fugamon0.on_talk
def talk():    # section 5
    recruitable(fugamon0, line=t5.u0)

@fugamon1.on_talk
def talk():    # section 6
    recruitable(fugamon1, line=t6.u0)

@fugamon2.on_talk
def talk():    # section 7
    recruitable(fugamon2, line=t7.u0)

@goblimon3.on_talk
def talk():    # section 8
    recruitable(goblimon3, line=t8.u0)

@goblimon4.on_talk
def talk():    # section 9
    recruitable(goblimon4, line=t9.u0)

@fugamon5.on_talk
def talk():    # section 10
    recruitable(fugamon5, line=t10.u0)

@tsukaimon6.on_talk
def talk():    # section 11
    recruitable(tsukaimon6, line=t11.u0)

@tsukaimon7.on_talk
def talk():    # section 12
    recruitable(tsukaimon7, line=t12.u0)

@trees.on_step(0)
def step0():    # section 51
    tamer.walk(-1700, -1800, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_117, entry=1)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_117, entry=1)
        return step1()
    warp(Screen.misty_trees_118, entry=1)
    return step1()

@trees.on_step(1)
def step1():    # section 52
    tamer.walk(-2600, 4000, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_119, entry=1)
    misty_trees_maze_steps.add(1)
    if misty_trees_maze_steps == 10:
        misty_trees_maze_steps.set(0)
        warp(Screen.misty_trees_119, entry=1)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_117, entry=1)
    else:
        warp(Screen.misty_trees_121, entry=2)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 12, 51, 52)
