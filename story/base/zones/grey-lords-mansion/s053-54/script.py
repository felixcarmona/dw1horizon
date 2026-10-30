# The Python view of script 53 of DG.SCN: screen 54 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

mansion = screen(Screen.grey_lords_mansion_54)

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.OmniDisk, at=(1057, -1268), opened=trigger(704), facing=1024)
    spawn_chest(Item.AutoPilot, at=(1057, -920), opened=trigger(705), facing=1024)

@mansion.on_use(1)
def use1():    # section 81
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(211, -1810, wait=False)
    warp(Screen.grey_lords_mansion_56, entry=1)

@mansion.on_use(2)
def use2():    # section 82
    swing_door(1)
    sound(8, 1)
    wait(500)
    tamer.walk(-927, 576, wait=False)
    warp(Screen.grey_lords_mansion_55, entry=0)
    return

# the section table, in the order of the original header
sections(254, 81, 82)
