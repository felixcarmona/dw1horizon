# The Python view of script 198 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

lib = script(198)
piddomon0 = lib.npc(Species.Piddomon, slot=0)
gururumon1 = lib.npc(Species.Gururumon, slot=1)
piddomon2 = lib.npc(Species.Piddomon, slot=2)
gururumon3 = lib.npc(Species.Gururumon, slot=3)
piddomon4 = lib.npc(Species.Piddomon, slot=4)
gururumon5 = lib.npc(Species.Gururumon, slot=5)
megadramon = lib.npc(Species.Megadramon172, slot=6)
t10 = text.s198.sec10
t5 = text.s198.sec5
t53 = text.s198.sec53
t6 = text.s198.sec6
t7 = text.s198.sec7
t8 = text.s198.sec8
t9 = text.s198.sec9

@lib.on_enter
def enter():    # section 254
    spawn_chest(Item.HPChip, at=(-373, 4348), opened=trigger(690))
    spawn_chest(Item.MPChip, at=(384, 4392), opened=trigger(691))

@lib.on_step(0)
def step0():    # section 51
    tamer.walk(-2748, 3453, wait=False)
    warp(Screen.mt_infinity_222, entry=0)

@lib.on_step(1)
def step1():    # section 52
    tamer.walk(2801, 3497, wait=False)
    warp(253, entry=1)

@piddomon0.on_talk
def talk():    # section 5
    recruitable(piddomon0, line=t5.u0)

@gururumon1.on_talk
def talk():    # section 6
    recruitable(gururumon1, line=t6.u0)

@piddomon2.on_talk
def talk():    # section 7
    recruitable(piddomon2, line=t7.u0)

@gururumon3.on_talk
def talk():    # section 8
    recruitable(gururumon3, line=t8.u0)

@piddomon4.on_talk
def talk():    # section 9
    recruitable(piddomon4, line=t9.u0)

@gururumon5.on_talk
def talk():    # section 10
    recruitable(gururumon5, line=t10.u0)

@lib.on_step(2)
def step2():    # section 53
    if recruited(Species.Megadramon):
        return
    tamer.face(megadramon)
    wait(250)
    tamer.say(t53.u0)
    megadramon.say(t53.u1)
    tamer.say(t53.u2)
    megadramon.say(t53.u3)
    tamer.say(t53.u4)
    if ask(yes=t53.m0.o0, no=t53.m0.o1):
        tamer.run(43, 1754, camera=True)
        return
    else:
        tamer.say(t53.u5)
        fight(megadramon, escape=False)
        tamer.face(megadramon)
        megadramon.face(tamer)
        partner.face(megadramon)
        megadramon.say(t53.u6)
        megadramon.walk_away(0, 0, looks=3)
        megadramon.leave()
        glances.set(0)
        tamer.say(t53.u7)
        recruit(Species.Megadramon)
        engine.prosperity.add(3)
        camera.on(tamer, speed=15)
        camera.arrived()
        return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9, 10, 53)
