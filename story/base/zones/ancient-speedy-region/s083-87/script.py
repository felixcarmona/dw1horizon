# The Python view of script 83 of DG.SCN: screen 87 Ancient Speedy Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

region = screen(Screen.ancient_speedy_region_87)
saberdramon0 = region.npc(Species.Saberdramon, slot=0)
saberdramon1 = region.npc(Species.Saberdramon, slot=1)
darklizardmon2 = region.npc(Species.DarkLizardmon, slot=2)
darklizardmon3 = region.npc(Species.DarkLizardmon, slot=3)
t5 = text.s083.sec5
t6 = text.s083.sec6
t7 = text.s083.sec7
t8 = text.s083.sec8

@region.on_enter
def enter():    # section 254
    pass

@saberdramon0.on_talk
def talk():    # section 5
    recruitable(saberdramon0, line=t5.u0)

@saberdramon1.on_talk
def talk():    # section 6
    recruitable(saberdramon1, line=t6.u0)

@darklizardmon2.on_talk
def talk():    # section 7
    recruitable(darklizardmon2, line=t7.u0)

@darklizardmon3.on_talk
def talk():    # section 8
    recruitable(darklizardmon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8)
