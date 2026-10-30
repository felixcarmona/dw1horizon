# The Python view of script 78 of DG.SCN: screen 81 Ancient Glacial Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_glacial_region_81)
monochromon = region.npc(Species.Monochromon165, slot=0)
saberdramon = region.npc(Species.Saberdramon, slot=1)
brachiomon2 = region.npc(Species.Brachiomon, slot=2)
brachiomon3 = region.npc(Species.Brachiomon, slot=3)
t5 = text.s078.sec5
t6 = text.s078.sec6
t81 = text.s078.sec81
t82 = text.s078.sec82

@region.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 10:
        spawn_item(Item.Digimushrm, at=(-1850, -3450))
    roll = random.roll(99)
    if roll <= 7:
        spawn_item(Item.Digimushrm, at=(-150, 2250))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.RedBerry, at=(-2450, -550))

@monochromon.on_talk
def talk():    # section 5
    match pstat(34):
        case 0:
            say(t5.u0)
            pstat(34).add(1)
        case 1 | _:
            say(t5.u1)
            pstat(34).set(0)

@saberdramon.on_talk
def talk():    # section 6
    tamer.face(saberdramon)
    sound(8, 3)
    wait(750)
    match leomon_talks:
        case 0:
            say(t6.u0)
            leomon_talks.add(1)
        case 1:
            say(t6.u1)
            leomon_talks.add(1)
        case 2:
            say(t6.u2)
            leomon_talks.add(1)
        case 3:
            say(t6.u3)
            leomon_talks.add(1)
        case 4:
            say(t6.u4)
            leomon_talks.add(1)
        case 5 | _:
            say(t6.u5)
            leomon_talks.set(0)

@region.on_use(2)
def use2():    # section 82
    brachiomon2.play(29)
    wait(250)
    brachiomon2.say(t82.u0)
    match pstat(36):
        case 0:
            brachiomon2.play(30)
            wait(250)
            brachiomon2.say(t82.u1)
            brachiomon2.play(30)
            wait(250)
            brachiomon2.say(t82.u2)
            pstat(36).add(1)
            brachiomon2.play(31)
            wait(250)
        case 1 | _:
            brachiomon2.play(30)
            wait(250)
            brachiomon2.say(t82.u3)
            brachiomon2.play(30)
            wait(250)
            brachiomon2.say(t82.u4)
            pstat(36).set(0)
            brachiomon2.play(31)
            wait(250)

@brachiomon2.on_talk
def talk():    # section 7
    pass

@brachiomon3.on_talk
def talk():    # section 8
    pass

@region.on_use(1)
def use1():    # section 81
    narrator.say(t81.u0)
    tamer.say(t81.u1)
    if ask(yes=t81.m0.o0, no=t81.m0.o1):
        if bits >= 200:
            raw.store_random(prize_roll, 99)
            if prize_roll < 29:
                take(bits=200)
                narrator.say(t81.u3)
                give(Item.Meat)
                if engine.item_did_not_fit:
                    tamer.say(t81.u4)
                    pick_item()
                    take_picked(all=True)
                    give(Item.Meat)
            else:
                if prize_roll < 59:
                    raw.set_dialog_owner(narrator)
                    take(bits=200)
                    narrator.say(t81.u5)
                    give(Item.SmRecovery)
                    if engine.item_did_not_fit:
                        tamer.say(t81.u6)
                        pick_item()
                        take_picked(all=True)
                        give(Item.SmRecovery)
                else:
                    if prize_roll < 79:
                        raw.set_dialog_owner(narrator)
                        take(bits=200)
                        narrator.say(t81.u7)
                        give(Item.MoldyMeat)
                        if engine.item_did_not_fit:
                            tamer.say(t81.u8)
                            pick_item()
                            take_picked(all=True)
                            give(Item.MoldyMeat)
                    else:
                        if prize_roll <= 99:
                            raw.set_dialog_owner(narrator)
                            take(bits=200)
                            narrator.say(t81.u9)
                            if engine.item_did_not_fit:
                                tamer.say(t81.u10)
                                pick_item()
                                take_picked(all=True)
                                give(Item.MPFloppy)
                                return
                        return
                    return
                return
            return
        tamer.say(t81.u2)
        return
    return

# the section table, in the order of the original header
sections(254, 5, 6, 82, 7, 8, 81)
