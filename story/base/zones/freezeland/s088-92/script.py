# The Python view of script 88 of DG.SCN: screen 92 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

freezeland = screen(Screen.freezeland_92)
t51 = text.s088.sec51

@freezeland.on_enter
def enter():    # section 254
    pass

@freezeland.on_step(0)
def step0():    # section 51
    if back_dimension_portal == 1:
        tamer.walk(170, -956, wait=False)
        warp(Screen.back_dimension_226, entry=0, then=60)
    raw.store_digimon_type(partner_type)
    raw.store_digimon_value(partner_type, partner_attribute)
    if partner_attribute == 2:
        return
    narrator.say(t51.u0)
    hide_hud()
    tamer.run(45, -850, camera=True, wait=False)
    partner.run(349, -753, wait=False)
    tamer.arrived()
    partner.arrived()
    wait(500)
    tamer.turn(2949)
    wait(500)
    tamer.turn(1925)
    tamer.say(t51.u1)

@freezeland.on_step(1)
def step1():    # section 52
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
sections(254, 51, 52)
