# The Python view of script 116 of DG.SCN: screen 120 Misty Trees.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

trees = screen(Screen.misty_trees_120)
gabumon = trees.npc(Species.Gabumon139, slot=0)
goblimon1 = trees.npc(Species.Goblimon, slot=1)
goblimon2 = trees.npc(Species.Goblimon, slot=2)
tsukaimon = trees.npc(Species.Tsukaimon, slot=3)
darklizardmon = trees.npc(Species.DarkLizardmon, slot=4)
t5 = text.s116.sec5
t6 = text.s116.sec6
t7 = text.s116.sec7
t8 = text.s116.sec8
t9 = text.s116.sec9

@trees.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 13:
        spawn_item(Item.Digimushrm, at=(350, -1450))
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(50, 1350))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.Happymushrm, at=(-750, -2550))

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@goblimon2.on_talk
def talk():    # section 7
    recruitable(goblimon2, line=t7.u0)

@tsukaimon.on_talk
def talk():    # section 8
    recruitable(tsukaimon, line=t8.u0)

@darklizardmon.on_talk
def talk():    # section 9
    recruitable(darklizardmon, line=t9.u0)

@gabumon.on_talk
def talk():    # section 5
    say(t5.u0)
    fight(gabumon, escape=False)
    face(tamer)
    tamer.face(gabumon)
    partner.face(gabumon)
    tamer.arrived()
    partner.arrived()
    say(t5.u1)
    tamer.say(t5.u2)
    say(t5.u3)
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u4)
    say(t5.u5)
    tamer.play(19)
    wait(1000)
    tamer.say(t5.u6)
    say(t5.u7)
    hide_hud()
    walk_away(-330, -2751, looks=5)
    leave()
    glances.set(0)
    sound(8, 10)
    narrator.say(t5.u8)
    tamer.play(16)
    wait(1000)
    tamer.say(t5.u9)
    camera.on(tamer, speed=10)
    camera.arrived()
    recruit(Species.Gabumon)
    engine.prosperity.add(1)
    return

# the section table, in the order of the original header
sections(254, 6, 7, 8, 9, 5)
