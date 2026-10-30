# The Python view of script 207 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(207)
slot6 = lib.npc(None, slot=6)    # no NPC of the .MAP in this slot; the script spawns what stands here
t11 = text.s207.sec11

@lib.on_enter
def enter():    # section 254
    pass

@slot6.on_talk
def talk():    # section 11
    if recruited(Species.Vegiemon):
        if not trigger(186):
            trigger(186).set()
            say(t11.u44)
            camera.to(-2243, 1914, speed=30)
            camera.arrived()
            wait(1000)
            camera.on(tamer, speed=20)
            camera.arrived()
            say(t11.u45)
        roll = random.roll(3)    # Horizon: a big harvest 1 day in 4 (the original: roll(9), 1 in 10)
        if meat_farm_days >= 1 and roll <= 0:
            say(t11.u46)
            if has(Item.Sirloin, 99):
                say(t11.u47)
                return
            if has(Item.Sirloin, 95):
                say(t11.u48)
                give(Item.Sirloin, 5)
                narrator.say(t11.u49)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.Sirloin, 5)
            if engine.item_did_not_fit:
                raw.show_textbox(t11.u50)
                return
            narrator.say(t11.u51)
            say(t11.u52)
            meat_farm_days.set(0)
            return
        if meat_farm_days >= 1:
            say(t11.u53)
            if has(Item.Sirloin, 99):
                say(t11.u54)
                return
            if has(Item.Sirloin, 97):
                say(t11.u55)
                give(Item.Sirloin, 3)
                narrator.say(t11.u56)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.Sirloin, 3)
            if engine.item_did_not_fit:
                say(t11.u57)
                return
            narrator.say(t11.u58)
            meat_farm_days.set(0)
            return
        say(t11.u59)
        if ask(yes=t11.m2.o0, no=t11.m2.o1):
            while True:
                match choose(a=t11.m3.o0, b=t11.m3.o1, c=t11.m3.o2):
                    case "a":
                        if bits < 500:
                            say(t11.u60)
                            return
                        give(Item.Supercarrot)
                        if engine.item_did_not_fit:
                            raw.show_textbox(t11.u61)
                            return
                    case "b":
                        if bits < 500:
                            say(t11.u62)
                            return
                        give(Item.HawkRadish)
                        if engine.item_did_not_fit:
                            raw.show_textbox(t11.u63)
                            return
                    case "c" | _:
                        break
                take(bits=500)
                sound(0, 5)
                wait(250)
                say(t11.u64)
                if ask(yes=t11.m4.o0, no=t11.m4.o1):
                    pass
                else:
                    break
        say(t11.u65)
        return
    if recruited(Species.Palmon):
        if not meat_farm_expanded_explained:
            meat_farm_expanded_explained.set()
            say(t11.u25)
        roll = random.roll(3)    # Horizon: a big harvest 1 day in 4 (the original: roll(9), 1 in 10)
        if meat_farm_days >= 1 and roll <= 0:
            say(t11.u26)
            if has(Item.GiantMeat, 99):
                say(t11.u27)
                return
            if has(Item.GiantMeat, 95):
                say(t11.u28)
                give(Item.GiantMeat, 5)
                narrator.say(t11.u29)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.GiantMeat, 5)
            if engine.item_did_not_fit:
                raw.show_textbox(t11.u30)
                return
            narrator.say(t11.u31)
            say(t11.u32)
            meat_farm_days.set(0)
            return
        if meat_farm_days >= 1:
            say(t11.u33)
            if has(Item.GiantMeat, 99):
                say(t11.u34)
                return
            if has(Item.GiantMeat, 97):
                say(t11.u35)
                give(Item.GiantMeat, 3)
                narrator.say(t11.u36)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.GiantMeat, 3)
            if engine.item_did_not_fit:
                raw.show_textbox(t11.u37)
                return
            narrator.say(t11.u38)
            meat_farm_days.set(0)
            return
        say(t11.u39)
        if ask(yes=t11.m0.o0, no=t11.m0.o1):
            while True:
                if bits < 500:
                    break
                give(Item.GiantMeat)
                if engine.item_did_not_fit:
                    raw.show_textbox(t11.u41)
                    return
                take(bits=500)
                sound(0, 5)
                wait(250)
                say(t11.u42)
                if ask(yes=t11.m1.o0, no=t11.m1.o1):
                    pass
                else:
                    say(t11.u43)
                    return
            say(t11.u40)
            return
        say(t11.u43)
        return
    if meat_farm_explained:
        roll = random.roll(3)    # Horizon: a big harvest 1 day in 4 (the original: roll(9), 1 in 10)
        if meat_farm_days >= 1 and roll <= 0:
            say(t11.u10)
            if has(Item.Meat, 99):
                say(t11.u11)
                return
            if has(Item.Meat, 95):
                say(t11.u12)
                give(Item.Meat, 5)
                narrator.say(t11.u13)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.Meat, 5)
            if engine.item_did_not_fit:
                say(t11.u14)
                return
            narrator.say(t11.u15)
            say(t11.u16)
            meat_farm_days.set(0)
            return
        if meat_farm_days >= 1:
            say(t11.u17)
            if has(Item.Meat, 99):
                say(t11.u18)
                return
            if has(Item.Meat, 97):
                say(t11.u19)
                give(Item.Meat, 3)
                narrator.say(t11.u20)
                meat_farm_explained.set()
                meat_farm_days.set(0)
                return
            give(Item.Meat, 3)
            if engine.item_did_not_fit:
                say(t11.u21)
                return
            narrator.say(t11.u22)
            say(t11.u23)
            meat_farm_days.set(0)
            return
        say(t11.u24)
        return
    meat_farm_explained.set()
    say(t11.u0)
    tamer.say(t11.u1)
    say(t11.u2)
    tamer.say(t11.u3)
    say(t11.u4)
    if has(Item.Meat, 99):
        say(t11.u5)
        meat_farm_days.set(1)
        return
    if has(Item.Meat, 97):
        say(t11.u6)
        give(Item.Meat, 3)
        narrator.say(t11.u7)
        meat_farm_explained.set()
        meat_farm_days.set(0)
        return
    give(Item.Meat, 3)
    if engine.item_did_not_fit:
        say(t11.u8)
        return
    narrator.say(t11.u9)
    meat_farm_days.set(0)

# the section table, in the order of the original header
sections(254, 11)
