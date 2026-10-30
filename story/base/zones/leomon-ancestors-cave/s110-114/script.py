# The Python view of script 110 of DG.SCN: screen 114 Leomon Ancestor's Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

cave = screen(Screen.leomon_ancestors_cave_114)
drimogemon = cave.npc(Species.Drimogemon158, slot=0)
t5 = text.s110.sec5

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.OffChip, at=(-978, -2342), opened=trigger(667), facing=3072)

@drimogemon.on_talk
def talk():    # section 5
    say(t5.u0)
    return

# the section table, in the order of the original header
sections(254, 5)
