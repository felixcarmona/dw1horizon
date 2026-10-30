# The Python view of script 28 of DG.SCN: screen 27 Residential Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

area = screen(Screen.residential_area)
drimogemon = area.npc(Species.Drimogemon158, slot=0)
t5 = text.s028.sec5

@area.on_enter
def enter():    # section 254
    if not drimogemon_calmed:
        drimogemon.play(28)

@drimogemon.on_talk
def talk():    # section 5
    if recruited(Species.Ogremon):
        say(t5.u0)
        return
    if not drimogemon_calmed:
        play(28)
        sound(8, 10)
        say(t5.u1)
        play(28)
        tamer.play(16)
        wait(1000)
        tamer.say(t5.u2)
        sound(8, 10)
        say(t5.u3)
        fight(drimogemon, escape=False)
        tamer.face(drimogemon)
        face(tamer)
        partner.face(drimogemon)
        say(t5.u4)
        tamer.play(25)
        wait(1000)
        tamer.say(t5.u5)
        say(t5.u6)
        say(t5.u7)
        tamer.play(16)
        wait(1000)
        tamer.say(t5.u8)
        say(t5.u9)
        tamer.play(19)
        wait(1000)
        tamer.say(t5.u10)
        say(t5.u11)
        wait(500)
        tamer.play(anim.idle)
        while True:
            walk(1061, -767, wait=False)
            if glances >= 3:
                break
            glances.add(1)
            wait(1000)
            tamer.face(drimogemon)
            partner.face(drimogemon)
        glances.set(0)
        arrived()
        camera.on(tamer, speed=10)
        camera.arrived()
        drimogemon_calmed.set()
        return
    say(t5.u12)
    return

# the section table, in the order of the original header
sections(254, 5)
