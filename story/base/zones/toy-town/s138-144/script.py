# The Python view of script 138 of DG.SCN: screen 144 Toy Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.toy_town)
clearagumon = town.npc(Species.ClearAgumon, slot=0)
toyagumon = town.npc(Species.ToyAgumon, slot=1)
tankmon = town.npc(Species.Tankmon, slot=2)
t5 = text.s138.sec5
t6 = text.s138.sec6
t7 = text.s138.sec7

@town.on_enter
def enter():    # section 254
    pass

@clearagumon.on_talk
def talk():    # section 5
    say(t5.u0)
    if has_card(19) >= 1 and has_card(24) >= 1 and has_card(57) >= 1:
        if ask(yes=t5.m0.o0, no=t5.m0.o1):
            give(Item.XBandage)
            say(t5.u2)
            if engine.item_did_not_fit:
                tamer.say(t5.u3)
                return
            sound(0, 7)
            raw.take_card(19)
            raw.take_card(24)
            raw.take_card(57)
    else:
        tamer.say(t5.u1)

@toyagumon.on_talk
def talk():    # section 6
    say(t6.u0)

@tankmon.on_talk
def talk():    # section 7
    say(t7.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7)
