# The Python view of script 87 of DG.SCN: screen 91 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_91)
snowgoblimon0 = freezeland.npc(Species.SnowGoblimon, slot=0)
snowgoblimon1 = freezeland.npc(Species.SnowGoblimon, slot=1)
hyogamon = freezeland.npc(Species.Hyogamon, slot=2)
icedevimon3 = freezeland.npc(Species.IceDevimon, slot=3)
icedevimon4 = freezeland.npc(Species.IceDevimon, slot=4)
icedevimon5 = freezeland.npc(Species.IceDevimon, slot=5)
t10 = text.s087.sec10
t5 = text.s087.sec5
t6 = text.s087.sec6
t7 = text.s087.sec7
t8 = text.s087.sec8
t9 = text.s087.sec9

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-50, 2250))
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(-1050, -50))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.IceMushrm, at=(350, -2050))

@snowgoblimon0.on_talk
def talk():    # section 5
    recruitable(snowgoblimon0, line=t5.u0)

@snowgoblimon1.on_talk
def talk():    # section 6
    recruitable(snowgoblimon1, line=t6.u0)

@hyogamon.on_talk
def talk():    # section 7
    recruitable(hyogamon, line=t7.u0)

@icedevimon3.on_talk
def talk():    # section 8
    recruitable(icedevimon3, line=t8.u0)

@icedevimon4.on_talk
def talk():    # section 9
    recruitable(icedevimon4, line=t9.u0)

@icedevimon5.on_talk
def talk():    # section 10
    recruitable(icedevimon5, line=t10.u0)

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
sections(254, 5, 6, 7, 8, 9, 10, 51)
