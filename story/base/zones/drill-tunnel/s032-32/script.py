# The Python view of script 32 of DG.SCN: screen 32 Drill Tunnel.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

tunnel = screen(Screen.drill_tunnel_32)
drimogemon = tunnel.npc(Species.Drimogemon158, slot=0)
t52 = text.s032.sec52

@tunnel.on_enter
def enter():    # section 254
    if drimogemon_tunnel_dig_started and drimogemon_job_days >= 3:
        drill_tunnel_opened.set()
        objects[4].show()
        raw.entity_move_to(drimogemon, -1134, -566, 3, 0)
        wait(250)
        drimogemon.turn(3072)
        wait(250)
    if drimogemon_job_days < 3 and not recruited(Species.Drimogemon):
        drimogemon.play(29)

@tunnel.on_step(1)
def step1():    # section 52
    if recruited(Species.Drimogemon):
        return
    drimogemon.face(tamer)
    tamer.face(drimogemon)
    wait(250)
    if not drimogemon_tunnel_dig_started:
        drimogemon.say(t52.u0)
        drimogemon.turn(512)
        wait(250)
        drimogemon.play(29)
        drimogemon_tunnel_dig_started.set()
        drimogemon_job_days.set(0)
        tamer.walk(-334, -853)
        return
    if drimogemon_tunnel_dig_started and drimogemon_job_days >= 3:
        drimogemon.say(t52.u1)
        tamer.say(t52.u2)
        drimogemon.say(t52.u3)
        drimogemon.say(t52.u4)
        tamer.play(19)
        wait(750)
        tamer.say(t52.u5)
        tamer.play(anim.idle)
        drimogemon.say(t52.u6)
    else:
        drimogemon.say(t52.u7)
        drimogemon.turn(512)
        drimogemon.play(29)
        wait(250)
        tamer.walk(-334, -853)
        return
    drimogemon.walk_away(600, 1700, looks=3, pause=1250)
    drimogemon.send_to_city(line=t52.u8, species=Species.Drimogemon, sound=(8, 8), prosperity=2)

@drimogemon.on_talk
def talk():    # section 5
    return step1()

@tunnel.on_step(0)
def step0():    # section 51
    tamer.walk(-1996, -2148, wait=False)
    warp(Screen.foot_of_mt_panorama_23, entry=2)
    return

# the section table, in the order of the original header
sections(254, 52, 5, 51)
