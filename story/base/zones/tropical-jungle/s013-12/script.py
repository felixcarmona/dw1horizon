# The Python view of script 13 of DG.SCN: screen 12 Tropical Jungle.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

jungle = screen(Screen.tropical_jungle_12)
piximon = jungle.npc(Species.Piximon173, slot=0)
muchomon1 = jungle.npc(Species.Muchomon, slot=1)
muchomon2 = jungle.npc(Species.Muchomon, slot=2)
j_mojyamon3 = jungle.npc(Species.JMojyamon, slot=3)
j_mojyamon4 = jungle.npc(Species.JMojyamon, slot=4)
t5 = text.s013.sec5
t6 = text.s013.sec6
t7 = text.s013.sec7
t8 = text.s013.sec8
t9 = text.s013.sec9

@jungle.on_enter
def enter():    # section 254
    spawn_chest(Item.MedRecovery, at=(1941, 142), opened=trigger(693))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(2950, 1550))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(650, -1150))
    roll = random.roll(99)
    if roll <= 5:
        spawn_item(Item.Digimushrm, at=(3750, -1750))
    roll = random.roll(99)
    if roll <= 2:
        spawn_item(Item.OrangeBana, at=(-2850, -750))

@piximon.on_talk
def talk():    # section 5
    say(t5.u0)
    tamer.say(t5.u1)
    sound(8, 6)
    say(t5.u2)
    tamer.play(16)
    if ask(yes=t5.m0.o0, no=t5.m0.o1):
        fight(piximon, escape=False)
        tamer.face(piximon)
        face(tamer)
        partner.face(piximon)
        tamer.face(piximon)
        partner.face(piximon)
        face(tamer)
        tamer.arrived()
        say(t5.u3)
        walk_away(-2444, -3233, looks=10, pause=500)
        leave()
        glances.set(0)
        sound(8, 3)
        narrator.say(t5.u4)
        engine.no_escape.clear()
        recruit(Species.Piximon)
        engine.prosperity.add(3)
        camera.on(tamer, speed=10)
        camera.arrived()
        return
    say(t5.u5)
    walk_away(-2444, -3233, looks=10, pause=500)
    leave()
    glances.set(0)

@muchomon1.on_talk
def talk():    # section 6
    recruitable(muchomon1, line=t6.u0)

@muchomon2.on_talk
def talk():    # section 7
    recruitable(muchomon2, line=t7.u0)

@j_mojyamon3.on_talk
def talk():    # section 8
    recruitable(j_mojyamon3, line=t8.u0)

@j_mojyamon4.on_talk
def talk():    # section 9
    recruitable(j_mojyamon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9)
