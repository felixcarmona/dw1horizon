# The Python view of script 3 of DG.SCN: screen 2 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

forest = screen(Screen.native_forest_2)
goblimon0 = forest.npc(Species.Goblimon, slot=0)
goblimon1 = forest.npc(Species.Goblimon, slot=1)
palmon = forest.npc(Species.Palmon164, slot=2)
goblimon3 = forest.npc(Species.Goblimon, slot=3)
goblimon4 = forest.npc(Species.Goblimon, slot=4)
t5 = text.s003.sec5
t6 = text.s003.sec6
t7 = text.s003.sec7
t8 = text.s003.sec8
t9 = text.s003.sec9

@forest.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.BlueApple, at=(-1250, 1650))
    roll = random.roll(99)
    if roll <= 29:
        spawn_item(Item.Digimushrm, at=(-350, -950))
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(1250, -450))

@goblimon0.on_talk
def talk():    # section 5
    recruitable(goblimon0, line=t5.u0)

@goblimon1.on_talk
def talk():    # section 6
    recruitable(goblimon1, line=t6.u0)

@goblimon3.on_talk
def talk():    # section 8
    recruitable(goblimon3, line=t8.u0)

@goblimon4.on_talk
def talk():    # section 9
    recruitable(goblimon4, line=t9.u0)

@palmon.on_talk(scene=True)
def talk():    # section 7
    match pstat(32):
        case 0:
            narrator.say(t7.u0)
            pstat(32).add(1)
        case 1:
            narrator.say(t7.u1)
            pstat(32).add(1)
        case 2:
            narrator.say(t7.u2)
            pstat(32).add(1)
        case 3 | _:
            narrator.say(t7.u3)
            sound(8, 12)
            face(tamer)
            wait(1000)
            fight(palmon, escape=False)
            face(tamer)
            tamer.face(palmon)
            partner.face(palmon)
            tamer.arrived()
            partner.arrived()
            sound(8, 12)
            say(t7.u4)
            tamer.play(19)
            tamer.say(t7.u5)
            tamer.play(19)
            tamer.say(t7.u6)
            tamer.play(anim.idle)
            say(t7.u7)
            walk_away(170, 1863, looks=3, pause=900)
            leave()
            glances.set(0)
            camera.on(tamer, speed=10)
            sound.jingle()
            narrator.say(t7.u8)
            pstat(32).set(0)
            recruit(Species.Palmon)
            engine.prosperity.add(1)

# the section table, in the order of the original header
sections(254, 5, 6, 8, 9, 7)
