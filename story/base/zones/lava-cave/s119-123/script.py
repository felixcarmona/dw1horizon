# The Python view of script 119 of DG.SCN: screen 123 Lava Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

cave = screen(Screen.lava_cave_123)
demimeramon = cave.npc(Species.DemiMeramon, slot=0)
t5 = text.s119.sec5

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.Protection, at=(330, 449), opened=trigger(676), facing=3072)

@demimeramon.on_talk
def talk():    # section 5
    say(t5.u0)

@cave.on_step(0)
def step0():    # section 51
    tamer.walk(5000, -5000, wait=False)
    warp(Screen.drill_tunnel_32, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 51)
