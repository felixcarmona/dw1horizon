# The Python view of script 120 of DG.SCN: screen 124 Lava Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

cave = screen(Screen.lava_cave_124)
slot0 = cave.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.OffChip, at=(-582, 1062), opened=trigger(694))
    spawn_chest(Item.Medicine, at=(-1129, 1032), opened=trigger(695))

@slot0.on_talk
def talk():    # section 5
    return

# the section table, in the order of the original header
sections(254, 5)
