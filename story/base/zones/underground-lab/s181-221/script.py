# The Python view of script 181 of DG.SCN: screen 221 Underground Lab.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lab = screen(Screen.underground_lab_221)
skullgreymon = lab.npc(Species.SkullGreymon148, slot=0)
t51 = text.s181.sec51

@lab.on_enter
def enter():    # section 254
    if not lab_skullgreymon_beaten:
        skullgreymon.play(28)

@lab.on_step(0)
def step0():    # section 51
    if lab_skullgreymon_beaten:
        return
    tamer.say(t51.u0)
    tamer.run(-835, -37, camera=True, wait=False)
    partner.run(-353, 32, wait=False)
    tamer.arrived()
    partner.arrived()
    tamer.face(skullgreymon)
    partner.face(skullgreymon)
    tamer.arrived()
    partner.arrived()
    skullgreymon.play(29, wait=True)
    skullgreymon.say(t51.u1)
    tamer.say(t51.u2)
    skullgreymon.say(t51.u3)
    tamer.say(t51.u4)
    sound(8, 13)
    skullgreymon.say(t51.u5)
    fight(skullgreymon, escape=False)
    lab_skullgreymon_beaten.set()
    skullgreymon.say(t51.u6)
    sound(8, 9)
    skullgreymon.play(28)
    wait(3000)
    skullgreymon.leave()
    tamer.turn(3072)
    tamer.say(t51.u7)
    camera.on(tamer, speed=10)
    camera.arrived()
    return

# the section table, in the order of the original header
sections(254, 51)
