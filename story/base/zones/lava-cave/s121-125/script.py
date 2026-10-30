# The Python view of script 121 of DG.SCN: screen 125 Lava Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

cave = screen(Screen.lava_cave_125)
demimeramon = cave.npc(Species.DemiMeramon, slot=0)
t5 = text.s121.sec5

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.SDefDisk, at=(515, 1428), opened=trigger(679), facing=3072)

@demimeramon.on_talk
def talk():    # section 5
    say(t5.u0)
    if has_card(30) < 1:
        return
    match choose(a=t5.m0.o0, b=t5.m0.o1):
        case "a":
            say(t5.u1)
            raw.take_card(30)
            give(bits=1500)
            return
        case "b":
            return
        case _:
            return

# the section table, in the order of the original header
sections(254, 5)
