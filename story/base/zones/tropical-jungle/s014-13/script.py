# The Python view of script 14 of DG.SCN: screen 13 Tropical Jungle.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

jungle = screen(Screen.tropical_jungle_13)
yanmamon0 = jungle.npc(Species.Yanmamon, slot=0)
yanmamon1 = jungle.npc(Species.Yanmamon, slot=1)
yanmamon2 = jungle.npc(Species.Yanmamon, slot=2)
tsukaimon = jungle.npc(Species.Tsukaimon, slot=3)
j_mojyamon4 = jungle.npc(Species.JMojyamon, slot=4)
j_mojyamon5 = jungle.npc(Species.JMojyamon, slot=5)
t10 = text.s014.sec10
t5 = text.s014.sec5
t6 = text.s014.sec6
t7 = text.s014.sec7
t8 = text.s014.sec8
t9 = text.s014.sec9

@jungle.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-2450, 1650))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(1350, 1850))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Deluxmushrm, at=(350, -3150))

@yanmamon0.on_talk
def talk():    # section 5
    recruitable(yanmamon0, line=t5.u0)

@yanmamon1.on_talk
def talk():    # section 6
    recruitable(yanmamon1, line=t6.u0)

@yanmamon2.on_talk
def talk():    # section 7
    recruitable(yanmamon2, line=t7.u0)

@tsukaimon.on_talk
def talk():    # section 8
    recruitable(tsukaimon, line=t8.u0)

@j_mojyamon4.on_talk
def talk():    # section 9
    recruitable(j_mojyamon4, line=t9.u0)

@j_mojyamon5.on_talk
def talk():    # section 10
    recruitable(j_mojyamon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
