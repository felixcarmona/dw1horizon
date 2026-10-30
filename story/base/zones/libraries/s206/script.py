# The Python view of script 206 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(206)
slot1 = lib.npc(None, slot=1)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot2 = lib.npc(None, slot=2)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot5 = lib.npc(None, slot=5)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot6 = lib.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
slot7 = lib.npc(None, slot=7)    # no NPC of the .MAP in this slot; the script spawns what stands here
t10 = text.s206.sec10
t11 = text.s206.sec11
t12 = text.s206.sec12
t6 = text.s206.sec6
t7 = text.s206.sec7

@lib.on_enter
def enter():    # section 254
    pass

@slot1.on_talk
def talk():    # section 6
    curling_opponent.set(0)
    if not recruited(Species.Penguinmon) and not penguinmon_curling_offered:
        say(t6.u0)
        tamer.say(t6.u1)
        say(t6.u2)
        tamer.say(t6.u3)
        say(t6.u4)
        tamer.say(t6.u5)
        say(t6.u6)
        penguinmon_curling_offered.set()
        walk(1905, 1667, wait=False)
        wait(500)
        tamer.walk(1905, 1667, wait=False)
        wait(500)
        partner.walk(1905, 1667, wait=False)
        wait(500)
        warp(Screen.freezeland_136, entry=1)
        return
    if not recruited(Species.Penguinmon):
        say(t6.u7)
        match choose(a=t6.m0.o0, b=t6.m0.o1):
            case "b":
                curling_match_pending.set(0)
                say(t6.u10)
                return
            case _:
                return
    else:
        if not curling_rink_intro_seen:
            curling_rink_intro_seen.set()
            say(t6.u8)
        curling_opponent.set(0)
        say(t6.u9)
        match choose(a=t6.m1.o0, b=t6.m1.o1):
            case "b":
                curling_match_pending.set(0)
                say(t6.u10)
                return
            case _:
                return
    say(t6.u11)
    pick = pick_item()
    if pick is Picked.EMPTY:
        tamer.say(t6.u12)
    else:
        if engine.arg in (Item.Digianchovy, Item.Digisnapper, Item.DigiTrout, Item.BlackTrout):
            take_picked()
        elif engine.arg in (Item.Digicatfish, Item.Digiseabass):
            take_picked()
        else:
            if engine.arg != 255:
                tamer.say(t6.u13)
            curling_match_pending.set(0)
            say(t6.u15)
            return
        say(t6.u14)
        warp(Screen.freezeland_136, entry=1)
        return
    curling_match_pending.set(0)
    say(t6.u15)

@slot5.on_talk
def talk():    # section 10
    if curling_result == 0:
        slot1.say(t10.u0)
        return
    if curling_result == 2:
        slot1.say(t10.u1)
        if not medal.perfect_curling:
            medal.perfect_curling.set()
            sound(0, 7)
            narrator.say(t10.u2)
    slot1.say(t10.u3)
    tamer.say(t10.u4)
    slot1.say(t10.u5)
    slot1.walk_away(-105, 1821, looks=3)
    slot1.send_to_city(line=t10.u6, species=Species.Penguinmon)

@slot6.on_talk
def talk():    # section 11
    if curling_result == 0:
        slot1.say(t11.u0)
        return
    if curling_result == 2:
        slot1.say(t11.u1)
        if not medal.perfect_curling:
            medal.perfect_curling.set()
            sound(0, 7)
            narrator.say(t11.u2)
    slot1.say(t11.u3)
    slot1.say(t11.u4)
    raw.store_random(prize_roll, 49)
    while True:
        if prize_roll <= 0:
            give(Item.Rooster)
            random_roll.set(85)
        elif prize_roll <= 5:
            give(Item.Restore)
            random_roll.set(11)
        elif prize_roll <= 15:
            give(Item.OmniDisk)
            random_roll.set(18)
        elif prize_roll <= 22:
            give(Item.GiantMeat)
            random_roll.set(39)
        elif prize_roll <= 30:
            give(Item.LrgRecovery)
            random_roll.set(2)
        elif prize_roll <= 50:
            give(Item.MediumMP)
            random_roll.set(5)
        if not engine.item_did_not_fit:
            break
        slot1.say(t11.u5)
        engine.picker_mode.clear()
        call(Routine.choose_item)
        take_picked(all=True)
    narrator.say(t11.u6)
    camera.on(tamer, speed=10)
    camera.arrived()

@slot2.on_talk
def talk():    # section 7
    curling_opponent.set(1)
    slot1.say(t7.u0)
    match choose(a=t7.m0.o0, b=t7.m0.o1):
        case "a":
            slot1.say(t7.u1)
            pick = pick_item()
            if pick is Picked.EMPTY:
                tamer.say(t7.u2)
            else:
                if engine.arg in (Item.Digianchovy, Item.Digisnapper, Item.DigiTrout, Item.BlackTrout):
                    take_picked()
                elif engine.arg in (Item.Digicatfish, Item.Digiseabass):
                    take_picked()
                else:
                    if engine.arg != 255:
                        tamer.say(t7.u3)
                    curling_match_pending.set(0)
                    slot1.say(t7.u5)
                    return
                slot1.say(t7.u4)
                warp(Screen.freezeland_136, entry=1)
                return
            curling_match_pending.set(0)
            slot1.say(t7.u5)
        case "b":
            slot1.say(t7.u6)

@slot7.on_talk
def talk():    # section 12
    if curling_result == 0:
        slot1.say(t12.u0)
        return
    if curling_result == 2:
        slot1.say(t12.u1)
        if not medal.perfect_curling:
            medal.perfect_curling.set()
            sound(0, 7)
            narrator.say(t12.u2)
    slot1.say(t12.u3)
    raw.store_random(prize_roll, 49)
    while True:
        if prize_roll <= 0:
            give(Item.SilverBall)
            random_roll.set(103)
        elif prize_roll <= 1:
            give(Item.MetalArmor)
            random_roll.set(104)
        elif prize_roll <= 2:
            give(Item.Chainsaw)
            random_roll.set(105)
        elif prize_roll <= 3:
            give(Item.SmallSpear)
            random_roll.set(106)
        elif prize_roll <= 11:
            give(Item.SupRecovery)
            random_roll.set(3)
        elif prize_roll <= 21:
            give(Item.Restore)
            random_roll.set(11)
        elif prize_roll <= 33:
            give(Item.Omnipotent)
            random_roll.set(9)
        elif prize_roll <= 49:
            give(Item.Sirloin)
            random_roll.set(40)
        if not engine.item_did_not_fit:
            break
        slot1.say(t12.u4)
        engine.picker_mode.clear()
        call(Routine.choose_item)
        take_picked(all=True)
    narrator.say(t12.u5)
    camera.on(tamer, speed=10)
    camera.arrived()
    return

# the section table, in the order of the original header
sections(254, 6, 10, 11, 7, 12)
