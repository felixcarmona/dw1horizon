# The Python view of script 69 of DG.SCN: screen 72 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

savanna = screen(Screen.gear_savanna_72)
patamon = savanna.npc(Species.Patamon151, slot=0)
shimaunimon = savanna.npc(Species.ShimaUnimon, slot=1)
shamamon2 = savanna.npc(Species.Shamamon, slot=2)
shamamon3 = savanna.npc(Species.Shamamon, slot=3)
shamamon4 = savanna.npc(Species.Shamamon, slot=4)
t5 = text.s069.sec5
t6 = text.s069.sec6
t7 = text.s069.sec7
t8 = text.s069.sec8
t9 = text.s069.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 12:
        spawn_item(Item.Digimushrm, at=(-550, -650))
    roll = random.roll(99)
    if roll <= 8:
        spawn_item(Item.Digimushrm, at=(2450, -50))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Happymushrm, at=(-450, 350))

@patamon.on_talk
def talk():    # section 5
    sound(8, 7)
    say(t5.u0)
    fight(patamon, escape=False)
    tamer.face(patamon)
    face(tamer)
    partner.face(patamon)
    say(t5.u1)
    if ask(yes=t5.m0.o0, no=t5.m0.o1):
        fight(patamon, escape=False)
        tamer.face(patamon)
        face(tamer)
        partner.face(patamon)
        say(t5.u2)
        tamer.play(16)
        if ask(yes=t5.m1.o0, no=t5.m1.o1):
            fight(patamon, escape=False)
            tamer.face(patamon)
            face(tamer)
            partner.face(patamon)
            wait(250)
            play(28)
            sound(8, 7)
            wait(2000)
            say(t5.u3)
            tamer.play(8)
            tamer.say(t5.u4)
            play(anim.idle)
            tamer.play(anim.idle)
            say(t5.u5)
            tamer.say(t5.u6)
            say(t5.u7)
            tamer.play(19)
            tamer.say(t5.u8)
            say(t5.u9)
            walk_away(-1673, 122, looks=10, pause=500)
            send_to_city(line=t5.u10, species=Species.Patamon, sound=(8, 5))
            return
    say(t5.u11)
    camera.on(tamer, speed=10)
    camera.arrived()

@shimaunimon.on_talk
def talk():    # section 6
    recruitable(shimaunimon, line=t6.u0)

@shamamon2.on_talk
def talk():    # section 7
    recruitable(shamamon2, line=t7.u0)

@shamamon3.on_talk
def talk():    # section 8
    recruitable(shamamon3, line=t8.u0)

@shamamon4.on_talk
def talk():    # section 9
    recruitable(shamamon4, line=t9.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9)
