# The Python view of script 30 of DG.SCN: screen 29 Drill Tunnel 2nd floor.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

floor = screen(Screen.drill_tunnel_2nd_floor_29)
drimogemon = floor.npc(Species.Drimogemon158, slot=0)
t5 = text.s030.sec5

@floor.on_enter
def enter():    # section 254
    if not drill_tunnel_boulder_moved:
        raw.spawn_boulder(0)
        raw.set_rect_impassable(0, 42, 39, 9, 6)
    objects[0].show()

@floor.on_step(0)
def step0():    # section 51
    if not recruited(Species.Meramon):
        warp(Screen.lava_cave_30, entry=0)
        return
    warp(Screen.lava_cave_122, entry=0)

@drimogemon.on_talk
def talk():    # section 5
    if not drill_tunnel_boulder_moved:
        say(t5.u0)
        tamer.say(t5.u1)
        say(t5.u2)
        tamer.play(19)
        wait(1000)
        tamer.say(t5.u3)
        tamer.face(partner)
        tamer.play(anim.command)
        wait(1000)
        tamer.say(t5.u4)
        partner.walk(-337, 170, wait=False)
        tamer.face(partner)
        partner.arrived()
        wait(1000)
        partner.turn(2000)
        face(partner)
        tamer.face(partner)
        if partner.species in (Species.Botamon, Species.Koromon, Species.Agumon, Species.Betamon, Species.Punimon):
            pass
        elif partner.species in (Species.Tsunomon, Species.Gabumon, Species.Elecmon, Species.Poyomon, Species.Tokomon):
            pass
        elif partner.species in (Species.Patamon, Species.Kunemon, Species.Yuramon, Species.Tanemon, Species.Biyomon):
            pass
        elif partner.species != Species.Palmon and partner.species != Species.Penguinmon:
            partner.play(27)
            objects[0].hide()
            raw.move_boulder(0, 0, 50)
            sound(8, 3)
            wait(1000)
            raw.move_boulder(0, 0, 100)
            partner.walk(-337, 270, wait=False)
            sound(8, 3)
            wait(1000)
            raw.move_boulder(0, 0, 100)
            partner.walk(-337, 370, wait=False)
            sound(8, 3)
            wait(1000)
            raw.move_boulder(0, 0, 100)
            partner.walk(-337, 470, wait=False)
            sound(8, 3)
            wait(1000)
            raw.move_boulder(0, 10, 200)
            partner.walk(-337, 670, wait=False)
            sound(8, 3)
            wait(250)
            raw.move_boulder(0, 50, 300)
            sound(8, 3)
            wait(250)
            raw.move_boulder(0, 60, 400)
            sound(8, 3)
            wait(250)
            raw.move_boulder(0, 80, 500)
            sound(8, 3)
            wait(150)
            raw.move_boulder(0, 80, 600)
            sound(8, 3)
            wait(150)
            raw.move_boulder(0, 80, 600)
            sound(8, 3)
            wait(150)
            raw.move_boulder(0, 120, 300)
            sound(8, 3)
            wait(100)
            raw.move_boulder(0, 120, 100)
            sound(8, 3)
            wait(100)
            raw.move_boulder(0, 120, 100)
            sound(8, 3)
            wait(50)
            raw.despawn_boulder(0)
            sound(8, 3)
            wait(1000)
            partner.play(anim.idle)
            wait(250)
            objects[0].show()
            tamer.say(t5.u5)
            say(t5.u6)
            tamer.say(t5.u7)
            tamer.turn(2000)
            tamer.walk(-131, 1250)
            tamer.turn(2000)
            tamer.say(t5.u8)
            say(t5.u9)
            drill_tunnel_boulder_moved.set()
            warp(Screen.lava_cave_30, entry=0)
            return
        wait(1000)
        partner.play(27)
        wait(1000)
        partner.play(anim.tired_idle)
        wait(1500)
        say(t5.u11)
        tamer.walk(-337, 0)
        return
    say(t5.u10)

# the section table, in the order of the original header
sections(254, 51, 5)
