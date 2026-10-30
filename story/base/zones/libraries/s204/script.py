# The Python view of script 204 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(204)
t51 = text.s204.sec51

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    if cup_won.d_rank and cup_won.c_rank and cup_won.b_rank and cup_won.grade_a and cup_won.s_rank:
        if not medal.grade_cup:
            medal.grade_cup.set()
            sound(0, 7)
            narrator.say(t51.u0)
    if cup_won.version_1 and cup_won.version_2 and cup_won.version_3 and cup_won.version_4 and cup_won.version_0:
        if not medal.version_cup:
            medal.version_cup.set()
            sound(0, 7)
            narrator.say(t51.u1)
    if cup_won.fire and cup_won.battle and cup_won.air and cup_won.ice:
        if cup_won.earth and cup_won.mech and cup_won.filth:
            if not medal.type_cup:
                medal.type_cup.set()
                sound(0, 7)
                narrator.say(t51.u2)
    if cup_won.dino and cup_won.wing and cup_won.animal and cup_won.human:
        if not medal.special_cup:
            medal.special_cup.set()
            sound(0, 7)
            narrator.say(t51.u3)
    if partner.tournaments_won >= 100:
        if not medal.hundred_wins:
            medal.hundred_wins.set()
            sound(0, 7)
            narrator.say(t51.u4)
    return

# the section table, in the order of the original header
sections(254, 51)
