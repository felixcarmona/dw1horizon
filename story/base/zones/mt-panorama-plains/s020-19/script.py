# The Python view of script 20 of DG.SCN: screen 19 Mt. Panorama Plains.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

plains = screen(Screen.mt_panorama_plains)
mamemon = plains.npc(Species.Mamemon137, slot=0)
mudfrigimon1 = plains.npc(Species.MudFrigimon, slot=1)
mudfrigimon2 = plains.npc(Species.MudFrigimon, slot=2)
mudfrigimon3 = plains.npc(Species.MudFrigimon, slot=3)
t5 = text.s020.sec5
t6 = text.s020.sec6
t7 = text.s020.sec7
t8 = text.s020.sec8
t81 = text.s020.sec81

@plains.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 15:
        spawn_item(Item.Digimushrm, at=(-1850, -750))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(4150, -550))
    roll = random.roll(99)
    if roll <= 6:
        spawn_item(Item.Happymushrm, at=(1250, -4450))

@mamemon.on_talk
def talk():    # section 5
    sound.jingle()
    say(t5.u0)
    tamer.play(16)
    wait(1000)
    if ask(yes=t5.m0.o0, no=t5.m0.o1):
        engine.no_escape.set()
        fight()
        tamer.face(mamemon)
        partner.face(mamemon)
        face(tamer)
        tamer.arrived()
        say(t5.u1)
        play(29)
        wait(2000)
        tamer.play(20)
        wait(1000)
        tamer.say(t5.u2)
        tamer.play(anim.idle)
        play(28)
        wait(1000)
        play(anim.idle)
        face(tamer)
        sound.jingle()
        say(t5.u3)
        tamer.play(19)
        wait(1000)
        tamer.say(t5.u4)
        sound.jingle()
        say(t5.u5)
        walk_away(3800, -3100, looks=10, pause=500)
        leave()
        glances.set(0)
        sound(8, 8)
        narrator.say(t5.u6)
        engine.no_escape.clear()
        camera.on(tamer, speed=10)
        camera.arrived()
        engine.prosperity.add(3)
        recruit(Species.Mamemon)
        return
    say(t5.u7)
    walk_away(3800, -3100, looks=10, pause=500)
    leave()
    glances.set(0)

@mudfrigimon1.on_talk
def talk():    # section 6
    recruitable(mudfrigimon1, line=t6.u0)

@mudfrigimon2.on_talk
def talk():    # section 7
    recruitable(mudfrigimon2, line=t7.u0)

@mudfrigimon3.on_talk
def talk():    # section 8
    recruitable(mudfrigimon3, line=t8.u0)

@plains.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    narrator.say(t81.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 81)
