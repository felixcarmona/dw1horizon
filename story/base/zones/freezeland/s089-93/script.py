# The Python view of script 89 of DG.SCN: screen 93 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_93)
hyogamon0 = freezeland.npc(Species.Hyogamon, slot=0)
hyogamon1 = freezeland.npc(Species.Hyogamon, slot=1)
hyogamon2 = freezeland.npc(Species.Hyogamon, slot=2)
icedevimon3 = freezeland.npc(Species.IceDevimon, slot=3)
icedevimon4 = freezeland.npc(Species.IceDevimon, slot=4)
hyogamon5 = freezeland.npc(Species.Hyogamon, slot=5)
t10 = text.s089.sec10
t5 = text.s089.sec5
t6 = text.s089.sec6
t7 = text.s089.sec7
t8 = text.s089.sec8
t81 = text.s089.sec81
t9 = text.s089.sec9

@freezeland.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 11:
        spawn_item(Item.Digimushrm, at=(2250, -350))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-150, 450))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.IceMushrm, at=(-1450, -4150))
    freezeland_birdra_stop_unlocked.set()

@hyogamon0.on_talk
def talk():    # section 5
    recruitable(hyogamon0, line=t5.u0)

@hyogamon1.on_talk
def talk():    # section 6
    recruitable(hyogamon1, line=t6.u0)

@hyogamon2.on_talk
def talk():    # section 7
    recruitable(hyogamon2, line=t7.u0)

@icedevimon3.on_talk
def talk():    # section 8
    recruitable(icedevimon3, line=t8.u0)

@icedevimon4.on_talk
def talk():    # section 9
    recruitable(icedevimon4, line=t9.u0)

@hyogamon5.on_talk
def talk():    # section 10
    recruitable(hyogamon5, line=t10.u0)

@freezeland.on_use(1)
def use1():    # section 81
    tamer.turn(2468)
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
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81, 53)
