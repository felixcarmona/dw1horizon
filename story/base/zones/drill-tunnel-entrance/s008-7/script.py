# The Python view of script 8 of DG.SCN: screen 7 Drill Tunnel Entrance.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

entrance = screen(Screen.drill_tunnel_entrance)
slot0 = entrance.npc(None, slot=0)    # the .MAP has MarketManager here; the script spawns what stands here
t5 = text.s008.sec5
t51 = text.s008.sec51
t53 = text.s008.sec53

@entrance.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Happymushrm, at=(-2750, -1950))

@entrance.on_step(0)
def step0():    # section 51
    if not drill_tunnel_entrance_seen:
        camera.to(-5000, 2000, speed=30)
        tamer.turn(1117)
        camera.arrived()
        wait(2500)
        tamer.say(t51.u0)
        camera.on(tamer, speed=20)
        camera.arrived()
        drill_tunnel_entrance_seen.set()
        if not debug_mode:
            match choose(a=t51.m0.o0, b=t51.m0.o1):
                case "a" | _:
                    return
                case "b":
                    drill_tunnel_takeover_seen.set()
                    objects[5].show()
                    objects[6].hide()
                    camera.to(-5000, 2000, speed=30)
                    tamer.turn(1117)
                    camera.arrived()
                    wait(2500)
                    tamer.say(t51.u1)
                    camera.to(-2900, 0, speed=30)
                    camera.arrived()
                    wait(1000)
                    tamer.say(t51.u2)
                    spawn(Species.MarketManager, slot=0)
                    slot0.walk(-2028, -842, wait=False)
                    tamer.turn(1117)
                    slot0.arrived()
                    slot0.turn(1117)
                    slot0.arrived()
                    wait(500)
                    narrator.say(t51.u3)
                    slot0.walk(-1323, -815)
                    slot0.face(tamer)
                    slot0.arrived()
                    camera.on(tamer, speed=20)
                    camera.arrived()
                    tamer.face(slot0)
                    narrator.say(t51.u4)
                    tamer.say(t51.u5)
                    narrator.say(t51.u6)
                    tamer.say(t51.u7)
                    slot0.walk(-2333, 59)
                    slot0.turn(4000)
                    slot0.arrived()
                    return
    if not new_ogre_fortress_cleared or drill_tunnel_takeover_seen:
        return
    drill_tunnel_takeover_seen.set()
    objects[5].show()
    objects[6].hide()
    camera.to(-5000, 2000, speed=30)
    tamer.turn(1117)
    camera.arrived()
    wait(2500)
    tamer.say(t51.u1)
    camera.to(-2900, 0, speed=30)
    camera.arrived()
    wait(1000)
    tamer.say(t51.u2)
    spawn(Species.MarketManager, slot=0)
    slot0.walk(-2028, -842, wait=False)
    tamer.turn(1117)
    slot0.arrived()
    slot0.turn(1117)
    slot0.arrived()
    wait(500)
    narrator.say(t51.u3)
    slot0.walk(-1323, -815)
    slot0.face(tamer)
    slot0.arrived()
    camera.on(tamer, speed=20)
    camera.arrived()
    tamer.face(slot0)
    narrator.say(t51.u4)
    tamer.say(t51.u5)
    narrator.say(t51.u6)
    tamer.say(t51.u7)
    slot0.walk(-2333, 59)
    slot0.turn(4000)
    slot0.arrived()

@slot0.on_talk
def talk():    # section 5
    narrator.say(t5.u0)

@entrance.on_step(1)
def step1():    # section 52
    if native_forest_rockslide_cleared:
        tamer.walk(2000, -152, wait=False)
        warp(Screen.native_forest_111, entry=2)
    tamer.walk(2000, -152, wait=False)
    warp(Screen.native_forest_110, entry=1)

@entrance.on_step(2)
def step2():    # section 53
    if not recruited(Species.Drimogemon):
        return
    if new_ogre_fortress_cleared and not recruited(Species.Ogremon):
        return
    tamer.say(t53.u0)
    if ask(yes=t53.m0.o0, no=t53.m0.o1):
        tamer.run(-4017, -828, wait=False)
        warp(Screen.foot_of_mt_panorama_23, entry=2)
    tamer.walk(-4017, -828, wait=False)
    warp(Screen.drill_tunnel_24, entry=0)

# the section table, in the order of the original header
sections(254, 51, 5, 52, 53)
