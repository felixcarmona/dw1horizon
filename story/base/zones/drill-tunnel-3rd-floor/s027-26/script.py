# The Python view of script 27 of DG.SCN: screen 26 Drill Tunnel 3rd floor.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

floor = screen(Screen.drill_tunnel_3rd_floor)
drimogemon = floor.npc(Species.Drimogemon158, slot=0)
t5 = text.s027.sec5

@floor.on_enter
def enter():    # section 254
    drimogemon.play(29)

@drimogemon.on_talk(scene=True)
def talk():    # section 5
    tamer.face(drimogemon)
    wait(500)
    sound(8, 1)
    wait(500)
    sound(8, 1)
    wait(500)
    say(t5.u0)
    sound(8, 1)
    wait(500)
    sound(8, 1)
    wait(500)
    say(t5.u1)
    sound(8, 1)
    wait(500)
    sound(8, 1)
    wait(500)
    say(t5.u2)
    sound(8, 1)
    wait(500)
    face(tamer)
    raw.show_textbox(t5.u3)
    turn(296)
    wait(1000)
    play(29)
    return

# the section table, in the order of the original header
sections(254, 5)
