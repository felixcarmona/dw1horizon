# The Python view of script 113 of DG.SCN: screen 117 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

trees = screen(Screen.misty_trees_117)
kokatorimon = trees.npc(Species.Kokatorimon168, slot=0)
goblimon1 = trees.npc(Species.Goblimon, slot=1)
goblimon2 = trees.npc(Species.Goblimon, slot=2)
goblimon3 = trees.npc(Species.Goblimon, slot=3)
morishellmon4 = trees.npc(Species.MoriShellmon, slot=4)
morishellmon5 = trees.npc(Species.MoriShellmon, slot=5)
goblimon6 = trees.npc(Species.Goblimon, slot=6)
goblimon7 = trees.npc(Species.Goblimon, slot=7)
t10 = text.s113.sec10
t11 = text.s113.sec11
t12 = text.s113.sec12
t5 = text.s113.sec5
t54 = text.s113.sec54
t6 = text.s113.sec6
t7 = text.s113.sec7
t8 = text.s113.sec8
t9 = text.s113.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 19:
        spawn_item(Item.Digimushrm, at=(-1250, -3450))
    roll = random.roll(99)
    if roll <= 16:
        spawn_item(Item.Digimushrm, at=(-1650, -1750))
    roll = random.roll(99)
    if roll <= 12:
        spawn_item(Item.Digimushrm, at=(650, -1350))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Digipine, at=(650, -3350))

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@goblimon2.on_talk
def talk():    # section 7
    recruitable(goblimon2, line=t7.u0)

@goblimon3.on_talk
def talk():    # section 8
    recruitable(goblimon3, line=t8.u0)

@morishellmon4.on_talk
def talk():    # section 9
    recruitable(morishellmon4, line=t9.u0)

@morishellmon5.on_talk
def talk():    # section 10
    recruitable(morishellmon5, line=t10.u0)

@goblimon6.on_talk
def talk():    # section 11
    recruitable(goblimon6, line=t11.u0)

@goblimon7.on_talk
def talk():    # section 12
    recruitable(goblimon7, line=t12.u0)

@kokatorimon.on_talk
def talk():    # section 5
    sound.jingle()
    say(t5.u0)
    fight(kokatorimon, escape=False)
    face(tamer)
    tamer.face(kokatorimon)
    partner.face(kokatorimon)
    wait(500)
    say(t5.u1)
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u2)
    say(t5.u3)
    tamer.play(19)
    wait(1000)
    tamer.say(t5.u4)
    say(t5.u5)
    tamer.play(7)
    wait(1000)
    tamer.say(t5.u6)
    say(t5.u7)
    tamer.play(7)
    wait(1000)
    tamer.say(t5.u8)
    partner.play(11)
    wait(250)
    say(t5.u9)
    hide_hud()
    walk_away(-330, -2751, looks=10, pause=500)
    leave()
    glances.set(0)
    sound(8, 10)
    narrator.say(t5.u10)
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u11)
    camera.on(tamer, speed=10)
    camera.arrived()
    recruit(Species.Kokatorimon)
    engine.prosperity.add(2)

@trees.on_step(3)
def step3():    # section 54
    tamer.play(24)
    wait(1000)
    tamer.say(t54.u0)

@trees.on_step(1)
def step1():    # section 52
    if not misty_trees_dawn_visitor_spawned and not recruited(Species.Kokatorimon) and clock.hour >= 4 and clock.hour <= 6:
        spawn(Species.Devimon, slot=0, autotalk=True)
        misty_trees_dawn_visitor_spawned.set()

@trees.on_step(0)
def step0():    # section 51
    tamer.walk(-2500, -2900, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_116, entry=1)
    roll = random.roll(99)
    if roll < 49:
        warp(Screen.misty_trees_116, entry=1)
        return step2()
    warp(Screen.misty_trees_121, entry=2)
    return step2()

@trees.on_step(2)
def step2():    # section 53
    tamer.walk(2600, -2550, wait=False)
    if misty_trees_fog_spell_cast or cherrymon_met:
        warp(Screen.misty_trees_121, entry=0)
    roll = random.roll(99)
    if roll < 69:
        warp(Screen.misty_trees_121, entry=0)
    else:
        warp(Screen.misty_trees_116, entry=0)
    raw.end_script()

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 10, 11, 12, 5, 54, 52, 51, 53)
