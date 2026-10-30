# The Python view of script 71 of DG.SCN: screen 74 Gear Savanna.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

savanna = screen(Screen.gear_savanna_74)
psychemon0 = savanna.npc(Species.Psychemon, slot=0)
psychemon1 = savanna.npc(Species.Psychemon, slot=1)
akatorimon = savanna.npc(Species.Akatorimon, slot=2)
tsukaimon3 = savanna.npc(Species.Tsukaimon, slot=3)
tsukaimon4 = savanna.npc(Species.Tsukaimon, slot=4)
shamamon = savanna.npc(Species.Shamamon, slot=5)
t10 = text.s071.sec10
t5 = text.s071.sec5
t6 = text.s071.sec6
t7 = text.s071.sec7
t8 = text.s071.sec8
t81 = text.s071.sec81
t82 = text.s071.sec82
t9 = text.s071.sec9

@savanna.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 11:
        spawn_item(Item.Digimushrm, at=(1850, -50))
    roll = random.roll(99)
    if roll <= 17:
        spawn_item(Item.Digimushrm, at=(-350, 2050))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.SweetNut, at=(-350, -2350))
    roll = random.roll(99)
    if roll <= 0:
        spawn_item(Item.ChainMelon, at=(750, -3350))

@psychemon0.on_talk
def talk():    # section 5
    recruitable(psychemon0, line=t5.u0)

@psychemon1.on_talk
def talk():    # section 6
    recruitable(psychemon1, line=t6.u0)

@akatorimon.on_talk
def talk():    # section 7
    recruitable(akatorimon, line=t7.u0)

@tsukaimon3.on_talk
def talk():    # section 8
    recruitable(tsukaimon3, line=t8.u0)

@tsukaimon4.on_talk
def talk():    # section 9
    recruitable(tsukaimon4, line=t9.u0)

@shamamon.on_talk
def talk():    # section 10
    recruitable(shamamon, line=t10.u0)

@savanna.on_use(1)
def use1():    # section 81
    narrator.say(t81.u0)
    tamer.turn(1536)
    tamer.say(t81.u1)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            if bits >= 200:
                give(Item.SmRecovery)
                if engine.item_did_not_fit:
                    tamer.say(t81.u4)
                    return
                narrator.say(t81.u5)
                take(bits=200)
                raw.store_random(prize_roll, 99)
                if prize_roll >= 9:
                    return
            else:
                tamer.say(t81.u2)
                return
        case "b":
            if bits >= 500:
                give(Item.PortPotty)
                if engine.item_did_not_fit:
                    tamer.say(t81.u6)
                    return
                narrator.say(t81.u7)
                take(bits=500)
                raw.store_random(prize_roll, 99)
                if prize_roll >= 9:
                    return
            else:
                tamer.say(t81.u3)
                return
        case "c" | _:
            return
    tamer.say(t81.u8)
    narrator.say(t81.u9)
    give(Item.DoubleFlop)
    if engine.item_did_not_fit:
        engine.picker_mode.set()
        tamer.say(t81.u10)
        call(Routine.choose_item)
        take_picked(all=True)
        give(Item.SSpeedDisk)

@savanna.on_use(2)
def use2():    # section 82
    narrator.say(t82.u0)
    tamer.turn(2048)
    tamer.say(t82.u1)
    match choose(a=t82.m0.o0, b=t82.m0.o1, c=t82.m0.o2):
        case "a":
            if bits >= 200:
                partner.add(mp=100)
                take(bits=200)
                narrator.say(t82.u2)
            else:
                tamer.say(t82.u3)
                return
            return
        case "b":
            if bits >= 1800:
                partner.add(mp=1000)
                take(bits=1800)
                narrator.say(t82.u4)
            else:
                tamer.say(t82.u5)
                return
            return
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 81, 82)
