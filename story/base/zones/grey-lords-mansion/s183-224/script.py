# The Python view of script 183 of DG.SCN: screen 224 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

mansion = screen(Screen.grey_lords_mansion_224)
myotismon = mansion.npc(Species.Myotismon177, slot=0)
t60 = text.s183.sec60

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_step(0)
def step0():    # section 51
    return step9()

@mansion.on_step(9)
def step9():    # section 60
    spawn(Species.Myotismon177, slot=0)
    raw.entity_move_to(tamer, 276, -1057, 6, 0)
    raw.entity_move_to(partner, -688, 481, 6, 0)
    tamer.arrived()
    partner.arrived()
    tamer.turn(2128)
    partner.turn(3072)
    tamer.say(t60.u0)
    myotismon.say(t60.u1)
    myotismon.face(tamer)
    myotismon.say(t60.u2)
    tamer.say(t60.u3)
    myotismon.say(t60.u4)
    tamer.say(t60.u5)
    myotismon.say(t60.u6)
    tamer.face(myotismon)
    tamer.say(t60.u7)
    myotismon.say(t60.u8)
    tamer.say(t60.u9)
    myotismon.say(t60.u10)
    tamer.say(t60.u11)
    myotismon.say(t60.u12)
    tamer.say(t60.u13)
    myotismon.say(t60.u14)
    tamer.say(t60.u15)
    myotismon.say(t60.u16)
    if not recruited(Species.Greymon):
        myotismon.say(t60.u17)
        tamer.say(t60.u18)
        myotismon.say(t60.u19)
        tamer.say(t60.u20)
    else:
        tamer.say(t60.u21)
        myotismon.say(t60.u22)
        tamer.say(t60.u23)
        myotismon.say(t60.u24)
        recruit(Species.Myotismon)
    warp(Screen.grey_lords_mansion_52, entry=4)
    return

# the section table, in the order of the original header
sections(254, 51, 60)
