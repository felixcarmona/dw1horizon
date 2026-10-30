# The Python view of script 17 of DG.SCN: screen 16 Mangrove Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

region = screen(Screen.mangrove_region_16)
yanmamon0 = region.npc(Species.Yanmamon, slot=0)
yanmamon1 = region.npc(Species.Yanmamon, slot=1)
muchomon = region.npc(Species.Muchomon, slot=2)
j_mojyamon3 = region.npc(Species.JMojyamon, slot=3)
j_mojyamon4 = region.npc(Species.JMojyamon, slot=4)
j_mojyamon5 = region.npc(Species.JMojyamon, slot=5)
t10 = text.s017.sec10
t5 = text.s017.sec5
t6 = text.s017.sec6
t7 = text.s017.sec7
t8 = text.s017.sec8
t81 = text.s017.sec81
t9 = text.s017.sec9

@region.on_enter
def enter():    # section 254
    pass

@yanmamon0.on_talk
def talk():    # section 5
    recruitable(yanmamon0, line=t5.u0)

@yanmamon1.on_talk
def talk():    # section 6
    recruitable(yanmamon1, line=t6.u0)

@muchomon.on_talk
def talk():    # section 7
    recruitable(muchomon, line=t7.u0)

@j_mojyamon3.on_talk
def talk():    # section 8
    recruitable(j_mojyamon3, line=t8.u0)

@j_mojyamon4.on_talk
def talk():    # section 9
    recruitable(j_mojyamon4, line=t9.u0)

@j_mojyamon5.on_talk
def talk():    # section 10
    recruitable(j_mojyamon5, line=t10.u0)

@region.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    if not recruited(Species.Centarumon):
        narrator.say(t81.u0)
    else:
        narrator.say(t81.u1)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81)
