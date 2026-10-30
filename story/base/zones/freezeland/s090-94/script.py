# The Python view of script 90 of DG.SCN: screen 94 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_94)
snowgoblimon0 = freezeland.npc(Species.SnowGoblimon, slot=0)
snowgoblimon1 = freezeland.npc(Species.SnowGoblimon, slot=1)
icedevimon2 = freezeland.npc(Species.IceDevimon, slot=2)
icedevimon3 = freezeland.npc(Species.IceDevimon, slot=3)
t5 = text.s090.sec5
t6 = text.s090.sec6
t7 = text.s090.sec7
t8 = text.s090.sec8

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(1350, 850))
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-250, 1150))
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(-1550, -550))
    if digivolve_scene_seen:
        objects[35].show()

@snowgoblimon0.on_talk
def talk():    # section 5
    recruitable(snowgoblimon0, line=t5.u0)

@snowgoblimon1.on_talk
def talk():    # section 6
    recruitable(snowgoblimon1, line=t6.u0)

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

@freezeland.on_step(1)
def step1():    # section 52
    if not digivolve_scene_seen:
        return
    tamer.walk(-1158, 972, wait=False)
    warp(Screen.freezeland_137, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51, 52)
