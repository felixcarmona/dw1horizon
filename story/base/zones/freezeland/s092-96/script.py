# The Python view of script 92 of DG.SCN: screen 96 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_96)
snowagumon0 = freezeland.npc(Species.SnowAgumon, slot=0)
snowagumon1 = freezeland.npc(Species.SnowAgumon, slot=1)
snowgoblimon2 = freezeland.npc(Species.SnowGoblimon, slot=2)
snowgoblimon3 = freezeland.npc(Species.SnowGoblimon, slot=3)
t5 = text.s092.sec5
t6 = text.s092.sec6
t7 = text.s092.sec7
t8 = text.s092.sec8

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(750, -2650))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(150, 1350))

@snowagumon0.on_talk
def talk():    # section 5
    recruitable(snowagumon0, line=t5.u0)

@snowagumon1.on_talk
def talk():    # section 6
    recruitable(snowagumon1, line=t6.u0)

@snowgoblimon2.on_talk
def talk():    # section 7
    recruitable(snowgoblimon2, line=t7.u0)

@snowgoblimon3.on_talk
def talk():    # section 8
    recruitable(snowgoblimon3, line=t8.u0)

@freezeland.on_step(0)
def step0():    # section 51
    if not partner.sick or digivolve_scene_seen:
        return
    if partner.species in (Species.Agumon, Species.Greymon, Species.Tyrannomon, Species.Meramon, Species.Monochromon):
        jump_to_script(203, 51)
    if partner_type in (19, 32, 51, 1, 2):
        jump_to_script(203, 51)
    if partner_type in (15, 16, 29, 30, 43):
        jump_to_script(203, 51)
    if partner_type in (44, 21):
        jump_to_script(203, 51)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51)
