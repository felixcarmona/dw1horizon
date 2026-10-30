# The Python view of script 125 of DG.SCN: screen 130 Ogre Fortress.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

fortress = screen(Screen.ogre_fortress_130)
slot0 = fortress.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here

@fortress.on_enter
def enter():    # section 254
    spawn_chest(Item.SOffDisk, at=(-518, 2893), opened=trigger(673))
    spawn_chest(Item.Sirloin, at=(1247, -553), opened=trigger(674), facing=3072)
    spawn_chest(Item.OffChip, at=(1454, 2930), opened=trigger(675), facing=1024)
    spawn_chest(Item.DefChip, at=(-47, -2219), opened=trigger(683), facing=1024)

@slot0.on_talk
def talk():    # section 5
    return

# the section table, in the order of the original header
sections(254, 5)
