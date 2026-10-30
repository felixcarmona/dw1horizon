# The Python view of script 192 of DG.SCN: screen 236 File City, screen 237 File City.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

city_236 = screen(Screen.file_city_236)
city_237 = screen(Screen.file_city_237)
jijimon = city_236.npc(Species.Jijimon, slot=0)
greymon = city_236.npc(Species.Greymon129, slot=1)
airdramon = city_236.npc(Species.Airdramon131, slot=2)
t51 = text.s192.sec51

@city_236.on_enter
def enter():    # section 254
    pass

@city_236.on_step(0)
def step0():    # section 51
    call(Routine.load_ending)
    jijimon.face(tamer)
    greymon.face(tamer)
    airdramon.face(tamer)
    partner.walk(-340, -2263, wait=False)
    camera.to(172, -1848, speed=2)
    camera.arrived()
    wait(1000)
    jijimon.say(t51.u0)
    tamer.say(t51.u1)
    jijimon.say(t51.u2)
    narrator.say(t51.u3)
    airdramon.say(t51.u4)
    tamer.turn(0)
    wait(1500)
    tamer.turn(1024)
    wait(1500)
    tamer.turn(2048)
    wait(1500)
    tamer.turn(3072)
    wait(1500)
    tamer.say(t51.u5)
    jijimon.say(t51.u6)
    hide_hud()
    call(Routine.game_clear_save)
    tamer.face(partner)
    partner.face(tamer)
    wait(2000)
    tamer.say(t51.u7)
    hide_hud()
    wait(1500)
    jijimon.play(32)
    wait(2000)
    call(Routine.start_ending)
    return

# the section table, in the order of the original header
sections(254, 51)
