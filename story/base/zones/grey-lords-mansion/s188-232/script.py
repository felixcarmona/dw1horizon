# The Python view of script 188 of DG.SCN: screen 232 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

mansion = screen(Screen.grey_lords_mansion_232)

@mansion.on_enter
def enter():    # section 254
    spawn_chest(Item.Medicine, at=(-554, -1089), opened=trigger(700), facing=2048)
    spawn_chest(Item.DefDisk, at=(-271, -1089), opened=trigger(701), facing=2048)
    spawn_chest(Item.Protection, at=(12, -1089), opened=trigger(702), facing=2048)
    spawn_chest(Item.LargeMP, at=(330, -1089), opened=trigger(703), facing=2048)

@mansion.on_use(1)
def use1():    # section 81
    sound(8, 1)
    wait(500)
    tamer.walk(-1313, 385, wait=False)
    warp(Screen.grey_lords_mansion_53, entry=0)
    return

# the section table, in the order of the original header
sections(254, 81)
