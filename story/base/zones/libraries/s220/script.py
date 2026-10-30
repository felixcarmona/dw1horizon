# The Python view of script 220 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lib = script(220)
t83 = text.s220.sec83

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_use(3)
def use3():    # section 83
    if recruited(Species.Agumon):
        return
    sound(0, 0)
    narrator.say(t83.u0)
    if engine.prosperity >= 30:
        narrator.say(t83.u1)
        sound(0, 1)
        return
    if engine.prosperity >= 15:
        narrator.say(t83.u2)
        sound(0, 1)
        return
    narrator.say(t83.u3)
    sound(0, 1)
    return

# the section table, in the order of the original header
sections(254, 83)
