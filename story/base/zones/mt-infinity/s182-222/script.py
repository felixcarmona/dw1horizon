# The Python view of script 182 of DG.SCN: screen 222 Mt. Infinity.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

infinity = screen(Screen.mt_infinity_222)
metalgreymonvirus = infinity.npc(Species.MetalGreymonVirus136, slot=0)
t53 = text.s182.sec53

@infinity.on_enter
def enter():    # section 254
    pass

@infinity.on_step(0)
def step0():    # section 51
    tamer.walk(-370, -4600, wait=False)
    warp(254, entry=1)

@infinity.on_step(1)
def step1():    # section 52
    tamer.walk(-400, 4800, wait=False)
    warp(Screen.mt_infinity_225, entry=0)

@infinity.on_step(2)
def step2():    # section 53
    if mt_infinity_metalgreymon_beaten:
        return
    tamer.face(metalgreymonvirus)
    camera.to(-400, 2400, speed=15)
    camera.arrived()
    metalgreymonvirus.face(tamer)
    wait(250)
    metalgreymonvirus.say(t53.u0)
    tamer.play(20)
    wait(750)
    tamer.say(t53.u1)
    tamer.play(anim.idle)
    metalgreymonvirus.say(t53.u2)
    raw.set_dialog_owner(tamer)
    tamer.play(19)
    wait(750)
    tamer.say(t53.u3)
    tamer.play(anim.idle)
    metalgreymonvirus.say(t53.u4)
    tamer.say(t53.u5)
    metalgreymonvirus.say(t53.u6)
    fight(metalgreymonvirus, escape=False)
    tamer.face(metalgreymonvirus)
    metalgreymonvirus.face(tamer)
    partner.face(metalgreymonvirus)
    metalgreymonvirus.say(t53.u7)
    tamer.say(t53.u8)
    metalgreymonvirus.say(t53.u9)
    while True:
        metalgreymonvirus.walk(-400, -500, wait=False)
        if glances >= 3:
            break
        glances.add(1)
        wait(1000)
        tamer.face(metalgreymonvirus)
        partner.face(metalgreymonvirus)
    metalgreymonvirus.arrived()
    metalgreymonvirus.leave()
    glances.set(0)
    camera.on(tamer, speed=10)
    camera.arrived()
    mt_infinity_metalgreymon_beaten.set()
    return

# the section table, in the order of the original header
sections(254, 51, 52, 53)
