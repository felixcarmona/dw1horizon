# The Python view of script 50 of DG.SCN: screen 51 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_51)
golemon0 = mansion.npc(Species.Golemon, slot=0)
golemon1 = mansion.npc(Species.Golemon, slot=1)
t5 = text.s050.sec5
t51 = text.s050.sec51
t6 = text.s050.sec6

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.MPChip, at=(835, 2461), opened=trigger(650))
    spawn_chest(Item.Restore, at=(-2455, -1042), opened=trigger(651), facing=3072)
    spawn_chest(Item.AutoPilot, at=(44, -2504), opened=trigger(652), facing=3072)
    if mansion_trapdoor_fallen:
        objects[15].hide()

@golemon0.on_talk
def talk():    # section 5
    recruitable(golemon0, line=t5.u0)

@golemon1.on_talk
def talk():    # section 6
    recruitable(golemon1, line=t6.u0)

@mansion.on_step(0)
def step0():    # section 51
    if not mansion_trapdoor_fallen:
        tamer.say(t51.u0)
        sound(8, 4)
        objects[15].hide()
        wait(500)
        tamer.say(t51.u1)
        sound(8, 5)
        warp(Screen.grey_lords_mansion_63, entry=2, then=52)
        return
    tamer.say(t51.u2)
    sound(8, 4)
    sound(8, 5)
    warp(Screen.grey_lords_mansion_63, entry=2, then=52)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 51)
