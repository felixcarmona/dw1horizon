# The Python view of script 194 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(194)
vermilimon0 = lib.npc(Species.Vermilimon, slot=0)
piddomon1 = lib.npc(Species.Piddomon, slot=1)
piddomon2 = lib.npc(Species.Piddomon, slot=2)
vermilimon3 = lib.npc(Species.Vermilimon, slot=3)
piddomon4 = lib.npc(Species.Piddomon, slot=4)
devimon = lib.npc(Species.Devimon130, slot=5)
t5 = text.s194.sec5
t53 = text.s194.sec53
t6 = text.s194.sec6
t7 = text.s194.sec7
t8 = text.s194.sec8
t9 = text.s194.sec9

@lib.on_enter
def enter():    # section 254
    spawn_chest(Item.Sirloin, at=(3758, 1159), opened=trigger(686), facing=1024)
    if not mt_infinity_devimon_beaten:
        devimon.play(28)
        return

@lib.on_step(0)
def step0():    # section 51
    tamer.walk(3588, 1931, wait=False)
    warp(248, entry=1)

@lib.on_step(1)
def step1():    # section 52
    tamer.walk(-4289, 1108, wait=False)
    warp(Screen.mt_infinity_219, entry=1)

@vermilimon0.on_talk
def talk():    # section 5
    recruitable(vermilimon0, line=t5.u0)

@piddomon1.on_talk
def talk():    # section 6
    recruitable(piddomon1, line=t6.u0)

@piddomon2.on_talk
def talk():    # section 7
    recruitable(piddomon2, line=t7.u0)

@vermilimon3.on_talk
def talk():    # section 8
    recruitable(vermilimon3, line=t8.u0)

@piddomon4.on_talk
def talk():    # section 9
    recruitable(piddomon4, line=t9.u0)

@lib.on_step(2)
def step2():    # section 53
    if mt_infinity_devimon_beaten:
        return
    devimon.say(t53.u0)
    devimon.play(28)
    raw.entity_move_to_axis(devimon, 0, 1, 20)
    wait(3000)
    tamer.say(t53.u1)
    devimon.say(t53.u2)
    fight(devimon, escape=False)
    tamer.face(devimon)
    devimon.face(tamer)
    partner.face(devimon)
    devimon.say(t53.u3)
    devimon.say(t53.u4)
    tamer.say(t53.u5)
    devimon.say(t53.u6)
    while True:
        devimon.play(28)
        raw.entity_move_to(devimon, -4562, 41, 20, 0)
        if glances >= 3:
            break
        glances.add(1)
        wait(1000)
        tamer.face(devimon)
        partner.face(devimon)
    devimon.arrived()
    devimon.leave()
    glances.set(0)
    camera.on(tamer, speed=10)
    camera.arrived()
    mt_infinity_devimon_beaten.set()
    return

# the section table, in the order of the original header
sections(254, 51, 52, 5, 6, 7, 8, 9, 53)
