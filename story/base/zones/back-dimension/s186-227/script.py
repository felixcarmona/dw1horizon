# The Python view of script 186 of DG.SCN: screen 227 Back Dimension.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

dimension = screen(Screen.back_dimension_227)
tekkamon0 = dimension.npc(Species.Tekkamon, slot=0)
tekkamon1 = dimension.npc(Species.Tekkamon, slot=1)
bluemeramon2 = dimension.npc(Species.BlueMeramon, slot=2)
bluemeramon3 = dimension.npc(Species.BlueMeramon, slot=3)
t5 = text.s186.sec5
t6 = text.s186.sec6
t7 = text.s186.sec7
t8 = text.s186.sec8

@dimension.on_enter
def enter():    # section 254
    spawn_chest(Item.MPChip, at=(2108, 375), opened=trigger(709), facing=1024)
    spawn_chest(Item.QuickChip, at=(563, 2868), opened=trigger(708))
    spawn_chest(Item.DefChip, at=(-481, 2868), opened=trigger(710))
    spawn_chest(Item.BrainChip, at=(31, 2868), opened=trigger(711))

@dimension.on_step(0)
def step0():    # section 51
    tamer.walk(-376, -1201, wait=False)
    warp(Screen.back_dimension_226, entry=1)

@dimension.on_step(1)
def step1():    # section 52
    tamer.walk(1221, -413, wait=False)
    warp(Screen.back_dimension_228, entry=0)

@tekkamon0.on_talk
def talk():    # section 5
    recruitable(tekkamon0, line=t5.u0)

@tekkamon1.on_talk
def talk():    # section 6
    recruitable(tekkamon1, line=t6.u0)

@bluemeramon2.on_talk
def talk():    # section 7
    recruitable(bluemeramon2, line=t7.u0)

@bluemeramon3.on_talk
def talk():    # section 8
    say(t8.u0)
    recruit(Species.BlueMeramon)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8)
