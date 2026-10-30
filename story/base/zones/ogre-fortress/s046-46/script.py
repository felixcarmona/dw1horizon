# The Python view of script 46 of DG.SCN: screen 46 Ogre Fortress.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

fortress = screen(Screen.ogre_fortress_46)
gabumon0 = fortress.npc(Species.Gabumon139, slot=0)
gabumon1 = fortress.npc(Species.Gabumon139, slot=1)
agumon = fortress.npc(Species.Agumon, slot=2)
t5 = text.s046.sec5
t6 = text.s046.sec6
t7 = text.s046.sec7

@fortress.on_enter
def enter():    # section 254
    spawn_chest(Item.AutoPilot, at=(-1235, 1587), opened=trigger(670), facing=3072)
    if ogre_fortress_cleared:
        objects[8].hide()

@gabumon0.on_talk
def talk():    # section 5
    say(t5.u0)
    fight()

@gabumon1.on_talk
def talk():    # section 6
    say(t6.u0)
    fight()

@agumon.on_talk
def talk():    # section 7
    say(t7.u0)
    fight()

@fortress.on_step(0)
def step0():    # section 51
    if ogre_fortress_cleared:
        tamer.walk(500, 3100, wait=False)
        warp(Screen.ogre_fortress_130, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 51)
