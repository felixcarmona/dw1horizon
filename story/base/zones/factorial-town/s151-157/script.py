# The Python view of script 151 of DG.SCN: screen 157 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

town = screen(Screen.factorial_town_157)
andromon = town.npc(Species.Andromon160, slot=0)
t5 = text.s151.sec5

@town.on_enter
def enter():    # section 254
    pass

@town.on_step(0)
def step0():    # section 51
    warp(Screen.factorial_town_154, entry=2)

@andromon.on_talk
def talk():    # section 5
    if recruited(Species.Andromon):
        say(t5.u0)
        return
    if island_history_read:
        say(t5.u1)
        sound(8, 10)
        narrator.say(t5.u2)
        recruit(Species.Andromon)
        engine.prosperity.add(3)
        return
    if trigger(329):
        say(t5.u3)
        turn(2048)
        wait(1000)
        sound(8, 5)
        tamer.say(t5.u4)
        sound(8, 6)
        narrator.say(t5.u5)
        tamer.play(16)
        wait(750)
        tamer.say(t5.u6)
        tamer.play(anim.idle)
        say(t5.u7)
        turn(0)
        wait(1000)
        tamer.say(t5.u8)
        say(t5.u9)
        tamer.play(25)
        wait(750)
        tamer.say(t5.u10)
        tamer.play(anim.idle)
        say(t5.u11)
        tamer.say(t5.u12)
        say(t5.u13)
        tamer.say(t5.u14)
        island_history_read.set()
        return
    if recruited(Species.Numemon) and not factorial_town_reopened:
        say(t5.u15)
        tamer.play(19)
        wait(750)
        tamer.say(t5.u16)
        tamer.play(anim.idle)
        tamer.say(t5.u17)
        say(t5.u18)
        tamer.say(t5.u19)
        say(t5.u20)
        tamer.say(t5.u21)
        say(t5.u22)
        tamer.say(t5.u23)
        say(t5.u24)
        tamer.say(t5.u25)
        factorial_town_reopened.set()
        return
    if factorial_town_reopened:
        tamer.say(t5.u26)
        say(t5.u27)
        tamer.say(t5.u28)
        return
    if factory_giromon_beaten and not recruited(Species.Numemon) and not factory_shut_down:
        tamer.play(7)
        wait(500)
        tamer.say(t5.u29)
        say(t5.u30)
        tamer.play(7)
        wait(750)
        tamer.say(t5.u31)
        tamer.play(anim.idle)
        say(t5.u32)
        turn(2048)
        wait(1000)
        sound(8, 5)
        say(t5.u33)
        tamer.say(t5.u34)
        factory_shut_down.set()
        return
    if factory_shut_down:
        say(t5.u35)
        tamer.say(t5.u36)
        return
    if factory_check_refused:
        say(t5.u37)
        tamer.say(t5.u38)
        tamer.play(16)
        wait(1000)
        tamer.play(anim.idle)
        tamer.say(t5.u39)
        return
    say(t5.u40)
    if not factory_permit_required:
        say(t5.u41)
        return
    if not factory_giromon_beaten and factory_permit_required and not factory_check_refused:
        tamer.say(t5.u42)
        say(t5.u43)
        tamer.say(t5.u44)
        say(t5.u45)
        tamer.say(t5.u46)
        tamer.play(19)
        wait(250)
        say(t5.u47)
        tamer.say(t5.u48)
        tamer.play(anim.idle)
        wait(250)
        say(t5.u49)
        tamer.say(t5.u50)
        tamer.play(19)
        wait(250)
        say(t5.u51)
        tamer.play(22)
        wait(500)
        tamer.say(t5.u52)
        factory_check_refused.set()
    return

# the section table, in the order of the original header
sections(254, 51, 5)
