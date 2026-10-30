# The Python view of script 26 of DG.SCN: screen 25 Drill Tunnel 2nd floor.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

floor = screen(Screen.drill_tunnel_2nd_floor_25)
goblimon0 = floor.npc(Species.Goblimon, slot=0)
goblimon1 = floor.npc(Species.Goblimon, slot=1)
goblimon2 = floor.npc(Species.Goblimon, slot=2)
ogremon = floor.npc(Species.Ogremon154, slot=3)
agumon4 = floor.npc(Species.Agumon, slot=4)
agumon5 = floor.npc(Species.Agumon, slot=5)
t10 = text.s026.sec10
t5 = text.s026.sec5
t51 = text.s026.sec51
t52 = text.s026.sec52
t53 = text.s026.sec53
t6 = text.s026.sec6
t7 = text.s026.sec7
t9 = text.s026.sec9

@floor.on_enter
def enter():    # section 254
    call(Routine.load_dirt_cart)
    if drill_tunnel_progress == 3:
        call(Routine.dirt_cart_model, arg=0)
        raw.set_autotalk(goblimon0, 0)
        raw.set_autotalk(goblimon1, 0)
        raw.set_autotalk(goblimon2, 0)
    if drill_tunnel_progress == 4:
        call(Routine.dirt_cart_model, arg=1)
        raw.set_autotalk(goblimon0, 0)
        raw.set_autotalk(goblimon1, 0)
        raw.set_autotalk(goblimon2, 0)

@goblimon0.on_talk
def talk():    # section 5
    if drill_tunnel_progress >= 3:
        say(t5.u0)
        return
    recruitable(goblimon0, line=t5.u1)

@goblimon1.on_talk
def talk():    # section 6
    if drill_tunnel_progress >= 3:
        say(t6.u0)
        return
    recruitable(goblimon1, line=t6.u1)

@goblimon2.on_talk
def talk():    # section 7
    if drill_tunnel_progress >= 3:
        say(t7.u0)
        return
    recruitable(goblimon2, line=t7.u1)

@agumon4.on_talk
def talk():    # section 9
    say(t9.u0)

@agumon5.on_talk
def talk():    # section 10
    say(t10.u0)

@floor.on_step(0)
def step0():    # section 51
    if not new_ogre_fortress_cleared or recruited(Species.Ogremon):
        return
    tamer.walk(-165, 221, camera=True, wait=False)
    partner.walk(171, 615, wait=False)
    tamer.arrived()
    partner.arrived()
    agumon4.walk(-323, 93, wait=False)
    agumon5.walk(498, -51, wait=False)
    ogremon.walk(160, -193, wait=False)
    goblimon0.arrived()
    goblimon1.arrived()
    ogremon.arrived()
    tamer.turn(100)
    partner.turn(100)
    agumon4.face(tamer)
    agumon5.face(tamer)
    ogremon.face(tamer)
    ogremon.say(t51.u0)
    tamer.say(t51.u1)
    ogremon.say(t51.u2)
    tamer.say(t51.u3)
    ogremon.play(32)
    ogremon.say(t51.u4)
    ogremon.play(anim.idle)
    tamer.say(t51.u5)
    fight(agumon4, agumon5, ogremon, escape=False)
    agumon4.play(43)
    agumon5.play(43)
    ogremon.walk(89, -659)
    ogremon.turn(100)
    tamer.face(ogremon)
    partner.face(ogremon)
    ogremon.arrived()
    ogremon.play(28)
    wait(1500)
    ogremon.say(t51.u6)
    ogremon.play(29)
    tamer.play(19)
    wait(1000)
    tamer.say(t51.u7)
    tamer.play(anim.idle)
    ogremon.say(t51.u8)
    tamer.say(t51.u9)
    ogremon.say(t51.u10)
    tamer.say(t51.u11)
    ogremon.say(t51.u12)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u13)
    tamer.play(anim.idle)
    ogremon.say(t51.u14)
    tamer.play(7)
    wait(750)
    tamer.say(t51.u15)
    tamer.play(anim.idle)
    tamer.run(160, -193, camera=True)
    tamer.turn(100)
    raw.show_textbox(t51.u16)
    ogremon.say(t51.u17)
    ogremon.play(30)
    ogremon.face(tamer)
    ogremon.say(t51.u18)
    ogremon.run(119, -494)
    ogremon.face(tamer)
    tamer.say(t51.u19)
    ogremon.say(t51.u20)
    ogremon.run(155, 873, wait=False)
    if glances < 6:
        glances.add(1)
        wait(500)
        tamer.face(ogremon)
        partner.face(ogremon)
    ogremon.arrived()
    ogremon.send_to_city(line=t51.u21, species=Species.Ogremon, sound=(8, 8), prosperity=2, camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()

@floor.on_step(1)
def step1():    # section 52
    if drill_tunnel_progress == 3:
        tamer.say(t52.u0)
        tamer.run(-51, -1550)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if drill_tunnel_progress == 4:
        tamer.say(t52.u1)
        tamer.run(-51, -1550)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if recruited(Species.Meramon) and engine.prosperity >= 45:
        tamer.walk(-105, -2200, wait=False)
        warp(Screen.drill_tunnel_126, entry=0)
    tamer.walk(-105, -2200, wait=False)
    warp(Screen.drill_tunnel_3rd_floor, entry=0)
    return step2()

@floor.on_step(2)
def step2():    # section 53
    if drill_tunnel_progress == 3:
        tamer.say(t53.u0)
        tamer.run(-2253, 359)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    if drill_tunnel_progress == 4:
        tamer.say(t53.u1)
        tamer.run(-2253, 359)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 9, 10, 51, 52, 53)
