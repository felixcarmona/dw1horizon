# The Python view of script 45 of DG.SCN: screen 45 Ogre Fortress.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

fortress = screen(Screen.ogre_fortress_45)
gabumon0 = fortress.npc(Species.Gabumon139, slot=0)
gabumon1 = fortress.npc(Species.Gabumon139, slot=1)
gabumon2 = fortress.npc(Species.Gabumon139, slot=2)
t5 = text.s045.sec5
t6 = text.s045.sec6
t7 = text.s045.sec7

@fortress.on_enter
def enter():    # section 254
    spawn_chest(Item.DoubleFlop, at=(1092, 1169), opened=trigger(669), facing=1024)

@gabumon0.on_talk
def talk():    # section 5
    say(t5.u0)
    fight()

@gabumon1.on_talk
def talk():    # section 6
    say(t6.u0)
    fight()

@gabumon2.on_talk
def talk():    # section 7
    say(t7.u0)
    fight()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7)
