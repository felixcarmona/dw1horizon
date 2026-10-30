# The Python view of script 185 of DG.SCN: screen 226 Back Dimension.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

dimension = screen(Screen.back_dimension_226)
piddomon0 = dimension.npc(Species.Piddomon, slot=0)
piddomon1 = dimension.npc(Species.Piddomon, slot=1)
icedevimon2 = dimension.npc(Species.IceDevimon, slot=2)
icedevimon3 = dimension.npc(Species.IceDevimon, slot=3)
t5 = text.s185.sec5
t6 = text.s185.sec6
t60 = text.s185.sec60
t7 = text.s185.sec7
t8 = text.s185.sec8

@dimension.on_enter
def enter():    # section 254
    spawn_chest(Item.RayGun, at=(-2240, 1956), opened=trigger(707), facing=3072)

@dimension.on_step(0)
def step0():    # section 51
    tamer.walk(2718, 1041, wait=False)
    if back_dimension_portal == 1:
        warp(Screen.freezeland_92, entry=1)
    if back_dimension_portal == 2:
        warp(Screen.overdell_cemetery, entry=1)
    if back_dimension_portal == 3:
        warp(Screen.fortress_entrance, entry=1)

@dimension.on_step(1)
def step1():    # section 52
    tamer.walk(-2786, 1100, wait=False)
    warp(Screen.back_dimension_227, entry=1)

@dimension.on_step(9)
def step9():    # section 60
    tamer.turn(1024)
    wait(2000)
    tamer.say(t60.u0)
    tamer.walk(2150, 1950, camera=True)
    tamer.say(t60.u1)

@piddomon0.on_talk
def talk():    # section 5
    recruitable(piddomon0, line=t5.u0)

@piddomon1.on_talk
def talk():    # section 6
    recruitable(piddomon1, line=t6.u0)

@icedevimon2.on_talk
def talk():    # section 7
    recruitable(icedevimon2, line=t7.u0)

@icedevimon3.on_talk
def talk():    # section 8
    recruitable(icedevimon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 60, 5, 6, 7, 8)
