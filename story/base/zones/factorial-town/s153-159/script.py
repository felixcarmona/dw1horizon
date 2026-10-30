# The Python view of script 153 of DG.SCN: screen 159 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_159)
giromon = town.npc(Species.Giromon161, slot=0)
t5 = text.s153.sec5

@town.on_enter
def enter():    # section 254
    pass

@giromon.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.say(t5.u1)
    sound.jingle()
    say(t5.u2)
    tamer.say(t5.u3)
    say(t5.u4)
    say(t5.u5)
    sound.jingle()
    say(t5.u6)
    walk_away(3050, -150, looks=3)
    send_to_city(line=t5.u7, species=Species.Giromon, sound=(8, 10), prosperity=3)
    return

# the section table, in the order of the original header
sections(254, 5)
