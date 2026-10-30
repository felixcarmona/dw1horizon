# The Python view of script 29 of DG.SCN: screen 28 Underground Pond.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

pond = screen(Screen.underground_pond)
drimogemon = pond.npc(Species.Drimogemon158, slot=0)
t51 = text.s029.sec51
t81 = text.s029.sec81

@pond.on_enter
def enter():    # section 254
    call(Routine.load_dirt_cart)
    call(Routine.load_dirt_pile)
    if drimogemon_job_days >= 5 and drill_tunnel_progress < 3 and drill_tunnel_progress >= 1:
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_pile_shrink)
        call(Routine.dirt_cart_model, arg=2)
        pstat(19).set(2)
        objects[19].show()
        objects[18].show()
        underground_pond_dig_work.set(10)
        return
    drimogemon.play(29)
    objects[19].show()
    objects[18].hide()
    if underground_pond_dig_work >= 5:
        objects[19].hide()
        objects[18].show()
        pstat(19).set(1)
    if underground_pond_dig_work >= 10:
        if drill_tunnel_progress < 3:
            objects[19].show()
            objects[18].show()
            pstat(19).set(2)
    if drill_tunnel_progress == 3:
        call(Routine.dirt_cart_model, arg=0)
    if drill_tunnel_progress == 4:
        call(Routine.dirt_cart_model, arg=1)
    if underground_pond_dig_work < 8:
        raw.set_rect_impassable(0, 69, 41, 3, 2)

@pond.on_step(1)
def step1():    # section 52
    if pstat(19) >= 2:
        return
    return L8()

@pond.on_step(0)
def step0():    # section 51
    if pstat(19) < 1:
        return L8()

@pond.on_use(1)
def use1():    # section 81
    if drill_tunnel_progress == 2:
        narrator.say(t81.u0)
        drill_tunnel_progress.set(3)
        call(Routine.dirt_cart_model, arg=0)
        call(Routine.dirt_pile_shrink)

@drimogemon.on_talk
def talk():    # section 5
    return

def L8():    # shared code (the disc's label L8)
    drimogemon.face(tamer)
    tamer.face(drimogemon)
    drimogemon.arrived()
    if underground_pond_dig_work >= 10:
        drimogemon.say(t51.u0)
        drimogemon.turn(1900)
        drimogemon.arrived()
        tamer.walk(2735, 1203, camera=True)
        drimogemon.play(29)
        return
    if drill_tunnel_progress == 4:
        drimogemon.say(t51.u1)
        call(Routine.dirt_cart_model, arg=2)
        give(bits=500)
        partner.add(offense=5)
        partner.add(defense=5)
        partner.add(max_hp=50)
        partner.add(tiredness=10)
        narrator.say(t51.u2)
        underground_pond_dig_work.add(1)
        drill_tunnel_progress.set(1)
        drimogemon.turn(1900)
        drimogemon.arrived()
        tamer.walk(2735, 1203, camera=True)
        drimogemon.play(29)
        return
    if drill_tunnel_progress == 3:
        drimogemon.say(t51.u3)
        tamer.walk(2735, 1203, camera=True)
        drimogemon.turn(1900)
        return
    if drill_tunnel_progress == 2:
        drimogemon.say(t51.u4)
        drimogemon.turn(1900)
        drimogemon.arrived()
        tamer.walk(2735, 1203, camera=True)
        drimogemon.play(29)
        return
    if drill_tunnel_progress == 1 and partner.tiredness >= 70:
        drimogemon.say(t51.u5)
        drimogemon.turn(1900)
        drimogemon.arrived()
        tamer.walk(2735, 1203, camera=True)
        drimogemon.play(29)
        return
    if drill_tunnel_progress == 1:
        drimogemon.say(t51.u6)
        if ask(yes=t51.m0.o0, no=t51.m0.o1):
            raw.set_textbox_size(entity(0), 21, 6)
            raw.show_textbox(t51.u17)
            hide_hud()
            tamer.walk(2735, 1203, camera=True)
            drill_tunnel_progress.set(2)
            return
    else:
        if not drimogemon_calmed:
            drimogemon.say(t51.u7)
            tamer.walk(2735, 1203, camera=True)
            drimogemon.turn(1900)
            drimogemon.arrived()
            drimogemon.play(29)
            return
        drill_tunnel_progress.set(1)
        drimogemon_job_days.set(0)
        drimogemon.say(t51.u8)
        tamer.say(t51.u9)
        drimogemon.say(t51.u10)
        tamer.say(t51.u11)
        drimogemon.say(t51.u12)
        tamer.say(t51.u13)
        camera.to(2027, 764, speed=20)
        camera.arrived()
        wait(1500)
        drimogemon.say(t51.u14)
        camera.on(tamer, speed=20)
        camera.arrived()
        drimogemon.say(t51.u15)
        tamer.say(t51.u16)
        if ask(yes=t51.m1.o0, no=t51.m1.o1):
            raw.set_textbox_size(entity(0), 21, 6)
            raw.show_textbox(t51.u17)
            hide_hud()
            tamer.walk(2735, 1203, camera=True)
            drill_tunnel_progress.set(2)
            return
    drimogemon.say(t51.u18)
    drimogemon.turn(1900)
    drimogemon.arrived()
    tamer.walk(2735, 1203, camera=True)
    drimogemon.play(29)

# the section table, in the order of the original header
sections(254, 52, 51, 81, 5)
