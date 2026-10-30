# The Python view of script 84 of DG.SCN: screen 88 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_88)
snowagumon = freezeland.npc(Species.SnowAgumon, slot=0)
snowgoblimon = freezeland.npc(Species.SnowGoblimon, slot=1)
icedevimon2 = freezeland.npc(Species.IceDevimon, slot=2)
icedevimon3 = freezeland.npc(Species.IceDevimon, slot=3)
t5 = text.s084.sec5
t6 = text.s084.sec6
t7 = text.s084.sec7
t8 = text.s084.sec8
t81 = text.s084.sec81

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-650, 1450))
    roll = random.roll(99)
    if roll <= 10:
        spawn_item(Item.Digimushrm, at=(-1150, -1750))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(50, -3150))

@snowagumon.on_talk
def talk():    # section 5
    recruitable(snowagumon, line=t5.u0)

@snowgoblimon.on_talk
def talk():    # section 6
    recruitable(snowgoblimon, line=t6.u0)

@icedevimon2.on_talk
def talk():    # section 7
    recruitable(icedevimon2, line=t7.u0)

@icedevimon3.on_talk
def talk():    # section 8
    recruitable(icedevimon3, line=t8.u0)

@freezeland.on_use(1)
def use1():    # section 81
    tamer.turn(943)
    narrator.say(t81.u0)

@freezeland.on_step(2)
def step2():    # section 53
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

@freezeland.on_step(0)
def step0():    # section 51
    tamer.walk(-1100, -5300, wait=False)
    if not canyon_elevator_ridden:
        warp(Screen.great_canyon_127, entry=1)
    warp(Screen.great_canyon_bridge, entry=1)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 81, 53, 51)
