# The Python view of script 62 of DG.SCN: screen 64 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

mansion = screen(Screen.grey_lords_mansion_64)
t81 = text.s062.sec81

@mansion.on_enter
def enter():    # section 254
    if mansion_book_trap_sprung:
        objects[4].show()

@mansion.on_use(1)
def use1():    # section 81
    if not mansion_book_trap_sprung:
        tamer.turn(91)
        wait(500)
        tamer.say(t81.u0)
        tamer.turn(3675)
        wait(500)
        tamer.turn(91)
        wait(500)
        tamer.turn(603)
        wait(500)
        tamer.turn(1115)
        wait(500)
        tamer.turn(1627)
        wait(500)
        tamer.turn(1115)
        wait(500)
        tamer.say(t81.u1)
        if ask(yes=t81.m0.o0, no=t81.m0.o1):
            tamer.walk(-314, -603, wait=False)
            partner.walk(-298, -335, wait=False)
            tamer.arrived()
            partner.arrived()
            tamer.turn(1115)
            partner.turn(91)
            narrator.say(t81.u2)
            tamer.say(t81.u3)
            sound(8, 4)
            objects[3].show()
            objects[4].hide()
            mansion_book_trap_sprung.set()
            tamer.play(26)
            raw.entity_move_to(tamer, 655, -663, 4, 0)
            raw.entity_move_to(partner, 694, -377, 4, 0)
            sound(8, 5)
            tamer.say(t81.u4)
            warp(Screen.grey_lords_mansion_57, entry=4, then=53)
            return
        tamer.say(t81.u5)

@mansion.on_use(2)
def use2():    # section 82
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(-1500, 615, wait=False)
    warp(Screen.grey_lords_mansion_53, entry=1)
    return

# the section table, in the order of the original header
sections(254, 81, 82)
