# The Python view of script 133 of DG.SCN: screen 138 Geko Swamp.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

swamp = screen(Screen.geko_swamp_138)
yanmamon0 = swamp.npc(Species.Yanmamon, slot=0)
yanmamon1 = swamp.npc(Species.Yanmamon, slot=1)
yanmamon2 = swamp.npc(Species.Yanmamon, slot=2)
gekomon3 = swamp.npc(Species.Gekomon, slot=3)
gekomon4 = swamp.npc(Species.Gekomon, slot=4)
gekomon5 = swamp.npc(Species.Gekomon, slot=5)
t10 = text.s133.sec10
t5 = text.s133.sec5
t6 = text.s133.sec6
t7 = text.s133.sec7
t8 = text.s133.sec8
t9 = text.s133.sec9

@swamp.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(850, -2150))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Digimushrm, at=(-1750, 1250))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.SpinyGreen, at=(-1850, 150))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.MuscleYam, at=(3450, 1450))

@yanmamon0.on_talk
def talk():    # section 5
    recruitable(yanmamon0, line=t5.u0)

@yanmamon1.on_talk
def talk():    # section 6
    recruitable(yanmamon1, line=t6.u0)

@yanmamon2.on_talk
def talk():    # section 7
    recruitable(yanmamon2, line=t7.u0)

@gekomon3.on_talk
def talk():    # section 8
    say(t8.u0)
    fight()

@gekomon4.on_talk
def talk():    # section 9
    say(t9.u0)
    fight()

@gekomon5.on_talk
def talk():    # section 10
    say(t10.u0)
    fight()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
