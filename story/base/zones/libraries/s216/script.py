# The Python view of script 216 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(216)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s216.sec51
t52 = text.s216.sec52

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    if not centar_clinic_intro_seen:
        centar_clinic_intro_seen.set()
        slot0.say(t51.u0)
    if not partner.injured and not partner.sick:
        slot0.say(t51.u4)
        match choose(a=t51.m0.o0, b=t51.m0.o1, c=t51.m0.o2):
            case "a":
                return L7()
            case "b":
                return L12()
            case "c" | _:
                return L13()
        return
    slot0.say(t51.u1)
    if bits >= 300:
        take(bits=300)
    else:
        slot0.say(t51.u2)
        take(bits=300)
    partner.walk(-200, -1039)
    slot0.face(partner)
    tamer.face(partner)
    wait(500)
    camera.on(partner, speed=20)
    camera.arrived()
    sound(8, 2)
    wait(2000)
    sound(8, 3)
    wait(1000)
    raw.remove_condition(32)
    raw.remove_condition(64)
    partner.play(11)
    wait(1000)
    slot0.say(t51.u3)
    if partner.tiredness >= 50:
        partner.set(tiredness=50)
    camera.on(tamer, speed=10)
    camera.arrived()
    return

@lib.on_step(1)
def step1():    # section 52
    slot0.say(t52.u0)
    match choose(a=t52.m0.o0, b=t52.m0.o1, c=t52.m0.o2):
        case "a":
            return L7()
        case "b":
            return L12()
        case "c" | _:
            return L13()

def L7():    # shared code (the disc's label L7)
    if partner.tiredness >= 80:
        slot0.say(t51.u5)
    elif partner.tiredness >= 50:
        slot0.say(t51.u6)
    elif partner.tiredness >= 20:
        slot0.say(t51.u7)
    else:
        slot0.say(t51.u8)
    raw.store_date(date_year)
    raw.add_minutes_to_date_at(date_year, 60)
    raw.advance_to_date_at(date_year)
    partner.add(hp=500)
    partner.add(mp=500)
    partner.sub(tiredness=20)
    warp(Screen.centar_clinic, entry=1)

def L12():    # shared code (the disc's label L12)
    slot0.say(t52.u1)
    match choose(a=t52.m1.o0, b=t52.m1.o1, c=t52.m1.o2):
        case "a":
            return L20()
        case "b":
            return L23()
        case "c" | _:
            return L13()

def L13():    # shared code (the disc's label L13)
    slot0.say(t52.u2)
    roll = random.roll(9)
    if roll <= 0:
        slot0.say(t52.u3)
        return
    if roll <= 1:
        slot0.say(t52.u4)
        return
    if roll <= 2:
        slot0.say(t52.u5)
        return
    if roll <= 3:
        slot0.say(t52.u6)
        return
    if roll <= 4:
        slot0.say(t52.u7)
        return
    if roll <= 5:
        slot0.say(t52.u8)
        return

def L20():    # shared code (the disc's label L20)
    if bits < 400:
        slot0.say(t52.u9)
        return L26()
    give(Item.Bandage)
    if engine.item_did_not_fit:
        slot0.say(t52.u10)
        return
    take(bits=400)
    return L26()

def L23():    # shared code (the disc's label L23)
    if bits < 1200:
        slot0.say(t52.u11)
        return L26()
    give(Item.Medicine)
    if engine.item_did_not_fit:
        slot0.say(t52.u12)
        return
    take(bits=1200)
    return L26()

def L26():    # shared code (the disc's label L26)
    slot0.say(t52.u13)
    match choose(a=t52.m2.o0, b=t52.m2.o1, c=t52.m2.o2):
        case "a":
            return L7()
        case "b":
            return L12()
        case "c" | _:
            return L13()

# the section table, in the order of the original header
sections(254, 51, 52)
