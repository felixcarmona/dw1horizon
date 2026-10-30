# The Python view of script 94 of DG.SCN: screen 98 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sanctuary = screen(Screen.ice_sanctuary_98)
icemon0 = sanctuary.npc(Species.Icemon, slot=0)
icemon1 = sanctuary.npc(Species.Icemon, slot=1)
bluemeramon = sanctuary.npc(Species.BlueMeramon, slot=2)
t5 = text.s094.sec5
t6 = text.s094.sec6
t7 = text.s094.sec7

@sanctuary.on_enter
def enter():    # section 254
    spawn_chest(Item.Restore, at=(-777, 519), opened=trigger(657))
    spawn_chest(Item.LrgRecovery, at=(793, -2801), opened=trigger(664), facing=1024)

@sanctuary.on_step(0)
def step0():    # section 51
    if angemon_voice_heard:
        tamer.walk(-43, -4563, wait=False)
        warp(Screen.ice_sanctuary_97, entry=1, then=5)
    tamer.walk(-43, -4563, wait=False)
    warp(Screen.ice_sanctuary_97, entry=1)

@sanctuary.on_step(1)
def step1():    # section 52
    tamer.walk(57, 3135, wait=False)
    warp(Screen.ice_sanctuary_99, entry=0)

@sanctuary.on_step(2)
def step2():    # section 53
    tamer.walk(2289, -1947, wait=False)
    warp(Screen.ice_sanctuary_103, entry=0)

@icemon0.on_talk
def talk():    # section 5
    recruitable(icemon0, line=t5.u0)

@icemon1.on_talk
def talk():    # section 6
    recruitable(icemon1, line=t6.u0)

@bluemeramon.on_talk
def talk():    # section 7
    recruitable(bluemeramon, line=t7.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 53, 5, 6, 7)
