# The Python view of script 42 of DG.SCN: screen 42 Great Canyon Bot. Area.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

area = screen(Screen.great_canyon_bot_area_42)
sandyanmamon0 = area.npc(Species.SandYanmamon, slot=0)
sandyanmamon1 = area.npc(Species.SandYanmamon, slot=1)
weedmon = area.npc(Species.Weedmon, slot=2)
gotsumon3 = area.npc(Species.Gotsumon, slot=3)
gotsumon4 = area.npc(Species.Gotsumon, slot=4)
gururumon = area.npc(Species.Gururumon, slot=5)
t10 = text.s042.sec10
t5 = text.s042.sec5
t51 = text.s042.sec51
t6 = text.s042.sec6
t7 = text.s042.sec7
t8 = text.s042.sec8
t9 = text.s042.sec9

@area.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(2950, -1350))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(-150, 1250))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.Deluxmushrm, at=(-150, -150))

@sandyanmamon0.on_talk
def talk():    # section 5
    recruitable(sandyanmamon0, line=t5.u0)

@sandyanmamon1.on_talk
def talk():    # section 6
    recruitable(sandyanmamon1, line=t6.u0)

@weedmon.on_talk
def talk():    # section 7
    recruitable(weedmon, line=t7.u0)

@gotsumon3.on_talk
def talk():    # section 8
    recruitable(gotsumon3, line=t8.u0)

@gotsumon4.on_talk
def talk():    # section 9
    recruitable(gotsumon4, line=t9.u0)

@gururumon.on_talk
def talk():    # section 10
    recruitable(gururumon, line=t10.u0)

@area.on_step(0)
def step0():    # section 51
    if partner.species in (Species.Devimon, Species.Airdramon, Species.MetalGreymonVirus, Species.Kabuterimon, Species.Angemon):
        pass
    elif partner.species in (Species.Birdramon, Species.Vademon, Species.Unimon, Species.Bakemon, Species.Giromon):
        pass
    elif partner.species != Species.Biyomon and partner.species != Species.Patamon and partner.species != Species.Kuwagamon and partner.species != Species.Megadramon and partner.species != Species.Piximon:
        partner.play(43)
        tamer.play(18)
        wait(2000)
        partner.play(44)
        wait(2000)
        partner.play(anim.idle)
        tamer.say(t51.u5)
        call(Routine.loop_once, arg=253)
        tamer.say(t51.u6)
        tamer.turn(2002)
        wait(1000)
        tamer.play(19)
        wait(750)
        tamer.say(t51.u7)
        tamer.play(anim.idle)
        tamer.say(t51.u8)
        tamer.say(t51.u9)
        return
    tamer.play(18)
    wait(1000)
    tamer.say(t51.u0)
    call(Routine.loop_once, arg=253)
    tamer.say(t51.u1)
    tamer.face(partner)
    wait(1000)
    partner.face(tamer)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u2)
    tamer.play(anim.idle)
    tamer.say(t51.u3)
    tamer.turn(2002)
    wait(1000)
    tamer.say(t51.u4)

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 51)
