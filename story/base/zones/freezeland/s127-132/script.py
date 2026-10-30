# The Python view of script 127 of DG.SCN: screen 132 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_132)
hyogamon0 = freezeland.npc(Species.Hyogamon, slot=0)
hyogamon1 = freezeland.npc(Species.Hyogamon, slot=1)
icedevimon2 = freezeland.npc(Species.IceDevimon, slot=2)
icedevimon3 = freezeland.npc(Species.IceDevimon, slot=3)
t5 = text.s127.sec5
t6 = text.s127.sec6
t7 = text.s127.sec7
t8 = text.s127.sec8

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 18:
        spawn_item(Item.Digimushrm, at=(1850, 2250))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.IceMushrm, at=(450, 950))

@hyogamon0.on_talk
def talk():    # section 5
    recruitable(hyogamon0, line=t5.u0)

@hyogamon1.on_talk
def talk():    # section 6
    recruitable(hyogamon1, line=t6.u0)

@icedevimon2.on_talk
def talk():    # section 7
    recruitable(icedevimon2, line=t7.u0)

@icedevimon3.on_talk
def talk():    # section 8
    recruitable(icedevimon3, line=t8.u0)

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
