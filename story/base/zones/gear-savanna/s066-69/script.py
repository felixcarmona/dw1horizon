# The Python view of script 66 of DG.SCN: screen 69 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_69)
shimaunimon0 = savanna.npc(Species.ShimaUnimon, slot=0)
shimaunimon1 = savanna.npc(Species.ShimaUnimon, slot=1)
tsukaimon = savanna.npc(Species.Tsukaimon, slot=2)
nisedrimogemon = savanna.npc(Species.NiseDrimogemon, slot=3)
t5 = text.s066.sec5
t6 = text.s066.sec6
t7 = text.s066.sec7
t8 = text.s066.sec8

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(1550, -1750))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(750, 50))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.PowerIce, at=(-1750, -3850))

@shimaunimon0.on_talk
def talk():    # section 5
    recruitable(shimaunimon0, line=t5.u0)

@shimaunimon1.on_talk
def talk():    # section 6
    recruitable(shimaunimon1, line=t6.u0)

@tsukaimon.on_talk
def talk():    # section 7
    recruitable(tsukaimon, line=t7.u0)

@nisedrimogemon.on_talk
def talk():    # section 8
    recruitable(nisedrimogemon, line=t8.u0)

@savanna.on_step(0)
def step0():    # section 51
    tamer.walk(200, -4700, wait=False)
    if drimogemon_tunnel_dig_started and drimogemon_job_days >= 3:
        drill_tunnel_opened.set()
    if drill_tunnel_opened:
        warp(Screen.foot_of_mt_panorama_23, entry=1)
    warp(Screen.foot_of_mt_panorama_22, entry=1)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51)
