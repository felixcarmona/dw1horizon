# The Python view of script 36 of DG.SCN: screen 36 Great Canyon Entrance.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

entrance = screen(Screen.great_canyon_entrance)
goblimon0 = entrance.npc(Species.Goblimon, slot=0)
goblimon1 = entrance.npc(Species.Goblimon, slot=1)
gotsumon2 = entrance.npc(Species.Gotsumon, slot=2)
gotsumon3 = entrance.npc(Species.Gotsumon, slot=3)
t5 = text.s036.sec5
t51 = text.s036.sec51
t52 = text.s036.sec52
t53 = text.s036.sec53
t6 = text.s036.sec6
t7 = text.s036.sec7
t8 = text.s036.sec8

@entrance.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-1350, -1850))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(3350, -2850))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-2450, 3250))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(2850, -1050))

@goblimon0.on_talk
def talk():    # section 5
    recruitable(goblimon0, line=t5.u0)

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@gotsumon2.on_talk
def talk():    # section 7
    recruitable(gotsumon2, line=t7.u0, joins=Species.Gotsumon)

@gotsumon3.on_talk
def talk():    # section 8
    recruitable(gotsumon3, line=t8.u0, joins=Species.Gotsumon)

@entrance.on_step(0)
def step0():    # section 51
    if not invisible_bridge_rumor_heard:
        tamer.play(15)
        wait(750)
        tamer.say(t51.u0)
        tamer.run(73, 971, camera=True)
    return L7()

@entrance.on_step(1)
def step1():    # section 52
    if not invisible_bridge_rumor_heard:
        tamer.play(15)
        wait(750)
        tamer.say(t52.u0)
        tamer.run(-782, 1580, camera=True)
    return L7()

@entrance.on_step(2)
def step2():    # section 53
    if invisible_bridge_rumor_heard:
        return L7()
    tamer.play(15)
    wait(750)
    tamer.say(t53.u0)
    tamer.run(856, 1137, camera=True)
    camera.on(tamer, speed=10)
    camera.arrived()
    return L7()

def L7():    # shared code (the disc's label L7)
    if not invisible_bridge_crossed and invisible_bridge_rumor_heard:
        tamer.turn(2000)
        wait(500)
        tamer.play(24)
        wait(750)
        tamer.say(t53.u1)
        tamer.play(anim.idle)
        tamer.say(t53.u2)
        tamer.walk(66, 3240, camera=True, wait=False)
        wait(1000)
        partner.walk(30, 2646, wait=False)
        tamer.arrived()
        partner.arrived()
        tamer.say(t53.u3)
        invisible_bridge_crossed.set()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 51, 52, 53)
