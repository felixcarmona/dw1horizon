# The Python view of script 21 of DG.SCN: screen 20 Path Thru Mt. Panorama.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

panorama = screen(Screen.path_thru_mt_panorama_20)
gotsumon0 = panorama.npc(Species.Gotsumon, slot=0)
goblimon1 = panorama.npc(Species.Goblimon, slot=1)
gotsumon2 = panorama.npc(Species.Gotsumon, slot=2)
goblimon3 = panorama.npc(Species.Goblimon, slot=3)
t5 = text.s021.sec5
t6 = text.s021.sec6
t7 = text.s021.sec7
t8 = text.s021.sec8

@panorama.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Digimushrm, at=(250, 2350))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-950, -1150))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Deluxmushrm, at=(1450, -1150))

@gotsumon0.on_talk
def talk():    # section 5
    recruitable(gotsumon0, line=t5.u0)

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@gotsumon2.on_talk
def talk():    # section 7
    recruitable(gotsumon2, line=t7.u0)

@goblimon3.on_talk
def talk():    # section 8
    recruitable(goblimon3, line=t8.u0)

@panorama.on_step(0)
def step0():    # section 51
    tamer.walk(-440, -5000, wait=False)
    if drimogemon_tunnel_dig_started and drimogemon_job_days >= 3:
        drill_tunnel_opened.set()
    if drill_tunnel_opened:
        warp(Screen.foot_of_mt_panorama_23, entry=0)
    warp(Screen.foot_of_mt_panorama_22, entry=0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51)
