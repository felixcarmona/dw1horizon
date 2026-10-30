# The Python view of script 33 of DG.SCN: screen 33 Lava Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

cave = screen(Screen.lava_cave_33)
demimeramon0 = cave.npc(Species.DemiMeramon, slot=0)
demimeramon1 = cave.npc(Species.DemiMeramon, slot=1)
t5 = text.s033.sec5
t6 = text.s033.sec6

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.OffChip, at=(2483, 247), opened=trigger(658), facing=1024)
    spawn_chest(Item.QuickChip, at=(2544, -110), opened=trigger(659), facing=1024)

@demimeramon0.on_talk
def talk():    # section 5
    say(t5.u0)

@demimeramon1.on_talk
def talk():    # section 6
    say(t6.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6)
