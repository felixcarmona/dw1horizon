# The Python view of script 25 of DG.SCN: screen 24 Drill Tunnel.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

tunnel = screen(Screen.drill_tunnel_24)
goblimon = tunnel.npc(Species.Goblimon, slot=0)
t5 = text.s025.sec5
t51 = text.s025.sec51
t52 = text.s025.sec52

@tunnel.on_enter
def enter():    # section 254
    call(Routine.load_dirt_cart)
    if drill_tunnel_progress == 3:
        call(Routine.dirt_cart_model, arg=0)
        raw.set_autotalk(goblimon, 0)
    if drill_tunnel_progress == 4:
        call(Routine.dirt_cart_model, arg=1)
        raw.set_autotalk(goblimon, 0)

@goblimon.on_talk
def talk():    # section 5
    if drill_tunnel_progress >= 3:
        say(t5.u0)
        return
    recruitable(goblimon, line=t5.u1)

@tunnel.on_step(0)
def step0():    # section 51
    if drill_tunnel_progress == 3:
        raw.entity_walk_to_entity(partner, 1, tamer)
        partner.arrived()
        partner.walk(1200, 1583)
        narrator.say(t51.u0)
        call(Routine.dirt_cart_model, arg=1)
        raw.entity_walk_to_entity(partner, 1, tamer)
        drill_tunnel_progress.set(4)

@tunnel.on_step(1)
def step1():    # section 52
    if drill_tunnel_progress == 4:
        tamer.say(t52.u0)
        tamer.run(453, 1815)
        camera.on(tamer, speed=10)
        camera.arrived()
    return

# the section table, in the order of the original header
sections(254, 5, 51, 52)
