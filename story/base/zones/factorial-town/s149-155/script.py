# The Python view of script 149 of DG.SCN: screen 155 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

town = screen(Screen.factorial_town_155)
geremon0 = town.npc(Species.Geremon, slot=0)
geremon1 = town.npc(Species.Geremon, slot=1)
geremon2 = town.npc(Species.Geremon, slot=2)
platinumsukamon3 = town.npc(Species.PlatinumSukamon, slot=3)
platinumsukamon4 = town.npc(Species.PlatinumSukamon, slot=4)
platinumsukamon5 = town.npc(Species.PlatinumSukamon, slot=5)
guardromon6 = town.npc(Species.Guardromon, slot=6)
guardromon7 = town.npc(Species.Guardromon, slot=7)
t10 = text.s149.sec10
t11 = text.s149.sec11
t12 = text.s149.sec12
t254 = text.s149.sec254
t5 = text.s149.sec5
t6 = text.s149.sec6
t7 = text.s149.sec7
t8 = text.s149.sec8
t9 = text.s149.sec9

@town.on_enter
def enter():    # section 254
    raw.store_date(date_year)
    if date_hour == 11 and date_minute >= 55:
        pass
    elif date_hour == 12 and date_minute <= 5:
        pass
    elif date_hour != 23 or date_minute < 55:
        if date_hour != 0 or date_minute > 5:
            return
    if not factory_guards_passed:
        tamer.play(24)
        wait(750)
        tamer.say(t254.u0)
        tamer.play(anim.idle)
        camera.to(2799, 74, speed=20)
        camera.arrived()
        camera.on(tamer, speed=15)
        camera.arrived()

@town.on_step(0)
def step0():    # section 51
    tamer.walk(-1061, -331, wait=False)
    warp(Screen.factorial_town_154, entry=3)

@town.on_step(1)
def step1():    # section 52
    tamer.walk(5589, -69, wait=False)
    warp(Screen.factorial_town_161, entry=1)

@guardromon7.on_talk
def talk():    # section 12
    sound(8, 9)
    say(t12.u0)

@guardromon6.on_talk
def talk():    # section 11
    sound(8, 9)
    say(t11.u0)
    if guard_shift_change_heard and clock.hour == 11 and clock.minute >= 55:
        pass
    elif guard_shift_change_heard and clock.hour == 12 and clock.minute <= 5:
        pass
    elif guard_shift_change_heard and clock.hour == 23 and clock.minute >= 55:
        pass
    elif not guard_shift_change_heard or clock.hour != 0 or clock.minute > 5:
        if guard_shift_change_heard:
            say(t11.u1)
            tamer.say(t11.u2)
            return
        if sewer_numemon_met and not factory_check_refused:
            tamer.say(t11.u3)
            tamer.face(partner)
            wait(250)
            tamer.play(22)
            partner.play(22)
            wait(250)
            tamer.play(22)
            partner.play(22)
            wait(250)
            tamer.face(guardromon6)
            partner.play(anim.idle)
            wait(500)
            tamer.play(19)
            wait(750)
            tamer.say(t11.u4)
            tamer.play(anim.idle)
            sound(8, 9)
            wait(250)
            say(t11.u5)
            tamer.say(t11.u6)
            say(t11.u7)
            tamer.play(25)
            wait(750)
            tamer.say(t11.u8)
            tamer.play(anim.idle)
            factory_permit_required.set()
            return
        if not factory_check_refused:
            return
        if factory_check_refused:
            tamer.say(t11.u9)
            match choose(a=t11.m0.o0, b=t11.m0.o1, c=t11.m0.o2):
                case "b":
                    sound(8, 9)
                    say(t11.u14)
                    match choose(a=t11.m2.o0, b=t11.m2.o1):
                        case _:
                            return
                    sound(8, 9)
                    say(t11.u15)
                    tamer.say(t11.u16)
                    return
                case "c" | _:
                    return
        sound(8, 9)
        say(t11.u10)
        match choose(a=t11.m1.o0, b=t11.m1.o1):
            case "a":
                sound(8, 9)
                say(t11.u11)
                return
            case "b":
                say(t11.u12)
                tamer.say(t11.u13)
                guard_shift_change_heard.set()
                return
            case _:
                return
    tamer.say(t11.u17)
    say(t11.u18)
    tamer.say(t11.u19)

@geremon0.on_talk
def talk():    # section 5
    recruitable(geremon0, line=t5.u0)

@geremon1.on_talk
def talk():    # section 6
    recruitable(geremon1, line=t6.u0)

@geremon2.on_talk
def talk():    # section 7
    recruitable(geremon2, line=t7.u0)

@platinumsukamon3.on_talk
def talk():    # section 8
    recruitable(platinumsukamon3, line=t8.u0)

@platinumsukamon4.on_talk
def talk():    # section 9
    recruitable(platinumsukamon4, line=t9.u0)

@platinumsukamon5.on_talk
def talk():    # section 10
    recruitable(platinumsukamon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 52, 12, 11, 5, 6, 7, 8, 9, 10)
