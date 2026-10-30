# The Python view of script 203 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lib = script(203)
t51 = text.s203.sec51

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    tamer.face(partner)
    tamer.arrived()
    tamer.say(t51.u0)
    raw.entity_walk_to_entity(partner, 0, tamer)
    partner.arrived()
    tamer.face(partner)
    partner.face(tamer)
    partner.play(23)
    wait(1500)
    sound(8, 1)
    wait(1500)
    sound(8, 2)
    wait(1500)
    partner.play(43)
    tamer.say(t51.u1)
    partner.play(anim.sleepy)
    warp(Screen.freezeland_137, entry=1, then=51)
    return

# the section table, in the order of the original header
sections(254, 51)
