# The Python view of script 23 of DG.SCN: screen 22 Foot of Mt. Panorama.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

panorama = screen(Screen.foot_of_mt_panorama_22)
flarerizamon0 = panorama.npc(Species.Flarerizamon, slot=0)
flarerizamon1 = panorama.npc(Species.Flarerizamon, slot=1)
aruraumon2 = panorama.npc(Species.Aruraumon, slot=2)
aruraumon3 = panorama.npc(Species.Aruraumon, slot=3)
tsukaimon4 = panorama.npc(Species.Tsukaimon, slot=4)
tsukaimon5 = panorama.npc(Species.Tsukaimon, slot=5)
goblimon6 = panorama.npc(Species.Goblimon, slot=6)
goblimon7 = panorama.npc(Species.Goblimon, slot=7)
t10 = text.s023.sec10
t11 = text.s023.sec11
t12 = text.s023.sec12
t5 = text.s023.sec5
t6 = text.s023.sec6
t7 = text.s023.sec7
t8 = text.s023.sec8
t9 = text.s023.sec9

@panorama.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(-550, 1650))
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-2650, 50))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.BigBerry, at=(-2450, -2450))

@flarerizamon0.on_talk
def talk():    # section 5
    recruitable(flarerizamon0, line=t5.u0)

@flarerizamon1.on_talk
def talk():    # section 6
    recruitable(flarerizamon1, line=t6.u0)

@aruraumon2.on_talk
def talk():    # section 7
    recruitable(aruraumon2, line=t7.u0)

@aruraumon3.on_talk
def talk():    # section 8
    recruitable(aruraumon3, line=t8.u0)

@tsukaimon4.on_talk
def talk():    # section 9
    recruitable(tsukaimon4, line=t9.u0)

@tsukaimon5.on_talk
def talk():    # section 10
    recruitable(tsukaimon5, line=t10.u0)

@goblimon6.on_talk
def talk():    # section 11
    recruitable(goblimon6, line=t11.u0)

@goblimon7.on_talk
def talk():    # section 12
    recruitable(goblimon7, line=t12.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 12)
