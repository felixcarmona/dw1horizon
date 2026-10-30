# The Python view of script 98 of DG.SCN: screen 102 Ice Sanctuary.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

sanctuary = screen(Screen.ice_sanctuary_102)
icemon = sanctuary.npc(Species.Icemon, slot=0)
hyogamon1 = sanctuary.npc(Species.Hyogamon, slot=1)
hyogamon2 = sanctuary.npc(Species.Hyogamon, slot=2)
t5 = text.s098.sec5
t52 = text.s098.sec52
t6 = text.s098.sec6
t7 = text.s098.sec7

@sanctuary.on_enter
def enter():    # section 254
    spawn_chest(Item.SupRecovery, at=(9, 1196), opened=trigger(660))
    spawn_chest(Item.LargeMP, at=(1223, 266), opened=trigger(661), facing=1024)
    if angemon_voice_heard:
        objects[0].show()

@sanctuary.on_step(0)
def step0():    # section 51
    warp(Screen.ice_sanctuary_101, entry=0)

@icemon.on_talk
def talk():    # section 5
    recruitable(icemon, line=t5.u0)

@hyogamon1.on_talk
def talk():    # section 6
    recruitable(hyogamon1, line=t6.u0)

@hyogamon2.on_talk
def talk():    # section 7
    recruitable(hyogamon2, line=t7.u0)

@sanctuary.on_step(1)
def step1():    # section 52
    if angemon_voice_heard:
        return
    tamer.play(22)
    sound(8, 9)
    wait(750)
    tamer.say(t52.u0)
    tamer.play(anim.idle)
    fade_to_white(2000)
    wait(2000)
    narrator.say(t52.u1)
    tamer.say(t52.u2)
    objects[0].show()
    call(Routine.fade_from_white)
    wait(2000)
    tamer.play(24)
    wait(750)
    tamer.say(t52.u3)
    tamer.play(23)
    wait(750)
    tamer.play(anim.idle)
    angemon_voice_heard.set()
    return

# the section table, in the order of the original header
sections(254, 51, 5, 6, 7, 52)
