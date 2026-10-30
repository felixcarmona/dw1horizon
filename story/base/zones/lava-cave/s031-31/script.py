# The Python view of script 31 of DG.SCN: screen 31 Lava Cave.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

cave = screen(Screen.lava_cave_31)
meramon = cave.npc(Species.Meramon133, slot=0)
t51 = text.s031.sec51

@cave.on_enter
def enter():    # section 254
    spawn_chest(Item.OffChip, at=(-582, 1062), opened=trigger(694))
    spawn_chest(Item.Medicine, at=(-1129, 1032), opened=trigger(695))

@cave.on_step(0)
def step0():    # section 51
    if recruited(Species.Tokomon):
        if recruited(Species.Meramon):
            return
        camera.on(meramon, speed=20)
        camera.arrived()
        meramon.say(t51.u14)
        meramon.face(tamer)
        raw.entity_walk_to_entity(partner, 1, tamer)
        partner.arrived()
        fight(meramon, escape=False)
        tamer.face(meramon)
        meramon.face(tamer)
        partner.face(meramon)
        meramon.say(t51.u15)
        tamer.say(t51.u16)
    else:
        recruit(Species.Tokomon)
        tamer.say(t51.u0)
        tamer.face(meramon)
        partner.face(meramon)
        camera.on(meramon, speed=20)
        camera.arrived()
        meramon.say(t51.u1)
        meramon.play(28)
        wait(1000)
        call(Routine.meramon_shake)
        sound(8, 4)
        wait(1000)
        sound(8, 4)
        wait(1000)
        sound(8, 4)
        wait(500)
        tamer.run(-1210, -193, wait=False)
        partner.run(-1468, -473, wait=False)
        tamer.arrived()
        partner.arrived()
        tamer.face(meramon)
        partner.face(meramon)
        native_forest_rockslide_cleared.set()
        wait(1000)
        tamer.play(7)
        wait(1000)
        tamer.say(t51.u2)
        wait(1000)
        meramon.face(tamer)
        meramon.say(t51.u3)
        fight(meramon, escape=False)
        tamer.face(meramon)
        meramon.face(tamer)
        partner.face(meramon)
        meramon.say(t51.u4)
        tamer.play(7)
        wait(1000)
        tamer.say(t51.u5)
        meramon.say(t51.u6)
    tamer.play(19)
    wait(1000)
    tamer.say(t51.u7)
    meramon.say(t51.u8)
    tamer.play(7)
    wait(1000)
    tamer.say(t51.u9)
    meramon.say(t51.u10)
    tamer.play(19)
    wait(1000)
    tamer.say(t51.u11)
    wait(1000)
    meramon.say(t51.u12)
    meramon.walk_away(691, -1990, looks=10, pause=500)
    meramon.send_to_city(line=t51.u13, species=Species.Meramon, sound=(8, 8), prosperity=2, camera=False)
    camera.on(tamer, speed=10)
    camera.arrived()

@cave.on_step(1)
def step1():    # section 52
    tamer.walk(1000, -4200, wait=False)
    if recruited(Species.Meramon):
        warp(Screen.lava_cave_122, entry=1)
    warp(Screen.lava_cave_30, entry=1)
    return

# the section table, in the order of the original header
sections(254, 51, 52)
