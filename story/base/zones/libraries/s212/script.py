# The Python view of script 212 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(212)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t71 = text.s212.sec71
t72 = text.s212.sec72
t73 = text.s212.sec73

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(20)
def step20():    # section 71
    engine.no_escape.clear()
    engine.battle_mode.set(0)
    entity(213).arrived()
    slot0.say(t71.u0)
    call(Routine.egg_choice)
    hide_hud()
    raw.call_digimon_routine(DigimonRoutine.dying_b)
    narrator.arrived()
    engine.music_mode.set(0)
    music(28)
    slot0.say(t71.u1)
    match choose(a=t71.m0.o0, b=t71.m0.o1):
        case "a":
            return L1()
        case "b":
            return L2()
        case _:
            return

@lib.on_step(21)
def step21():    # section 72
    engine.no_escape.clear()
    engine.battle_mode.set(0)
    entity(213).arrived()
    call(Routine.load_shop_library)
    if partner.hp != 0:
        raw.remove_condition(32)
        raw.remove_condition(64)
        partner.add(hp=9999)
        partner.add(mp=9999)
        slot0.say(t72.u0)
        entity(214).arrived()
        return L5()
    partner.add(hp=9999)
    partner.add(mp=9999)
    slot0.say(t72.u1)
    entity(214).arrived()
    return L5()

@lib.on_step(22)
def step22():    # section 73
    engine.no_escape.clear()
    engine.battle_mode.set(0)
    entity(213).arrived()
    slot0.say(t73.u0)
    if tamer.level != 0:
        tamer.sub(level=1)
        narrator.say(t73.u1)
    call(Routine.lost_all_lives)
    raw.call_digimon_routine(DigimonRoutine.dying_b)
    narrator.arrived()
    engine.music_mode.set(0)
    music(28)
    slot0.say(t73.u2)
    match choose(a=t73.m0.o0, b=t73.m0.o1):
        case "a":
            return L1()
        case "b":
            return L2()
        case _:
            return

def L1():    # shared code (the disc's label L1)
    while True:
        call(Routine.load_shop_library)
        entity(214).arrived()
        call(Routine.naming_and_intro, arg=3)
        slot0.say(t71.u2)
        match choose(a=t71.m1.o0, b=t71.m1.o1):
            case "a" | _:
                pass
            case "b":
                return L2()

def L2():    # shared code (the disc's label L2)
    pass

def L5():    # shared code (the disc's label L5)
    hide_hud()
    raw.store_digimon_type(partner_type)
    if partner_type in (3, 4, 17, 18):
        pass
    elif partner_type != 31 and partner_type != 32 and partner_type != 45 and partner_type != 46:
        if partner_type in (12, 54):
            roll = random.roll(99)
            if roll > 9:
                return
            engine.arg.set(26)
            raw.call_digimon_routine(DigimonRoutine.forced_evolution)
            wait(27500)
            narrator.say(t73.u4)
            return
        if partner_type == 50:
            roll = random.roll(99)
            if roll > 9:
                return
            engine.arg.set(59)
            raw.call_digimon_routine(DigimonRoutine.forced_evolution)
            wait(27500)
            narrator.say(t73.u5)
            return
        if partner_type != 20:
            return
        roll = random.roll(99)
        if roll > 49 or partner.discipline > 49:
            return
        engine.arg.set(6)
        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
        wait(27500)
        narrator.say(t73.u6)
        return
    roll = random.roll(99)
    if roll > 9:
        return
    engine.arg.set(37)
    raw.call_digimon_routine(DigimonRoutine.forced_evolution)
    wait(27500)
    narrator.say(t73.u3)

# the section table, in the order of the original header
sections(254, 71, 72, 73)
