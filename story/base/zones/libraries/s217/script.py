# The Python view of script 217 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(217)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s217.sec51

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    if recruited(Species.Meramon) and restaurant_chef == 0:
        slot0.say(t51.u0)
    elif recruited(Species.Tyrannomon) and restaurant_chef == 1:
        slot0.say(t51.u1)
        match narrator.choose(a=t51.m1.o0, b=t51.m1.o1, c=t51.m1.o2):
            case "a":
                if bits >= 400:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u17)
                        partner.add(offense=0)
                        partner.add(defense=1)
                        partner.add(speed=1)
                        partner.add(brain=0)
                        partner.add(max_hp=10)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=0)
                        partner.add(energy=18)
                        partner.add(weight=2)
                        take(bits=400)
                        narrator.say(t51.u18)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u19)
                        return
                else:
                    slot0.say(t51.u16)
                    return
            case "b":
                if bits >= 1000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u21)
                        partner.add(offense=0)
                        partner.add(defense=3)
                        partner.add(speed=2)
                        partner.add(brain=0)
                        partner.add(max_hp=30)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=4)
                        partner.add(discipline=0)
                        partner.add(energy=28)
                        partner.add(weight=3)
                        take(bits=1000)
                        narrator.say(t51.u22)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u23)
                        return
                else:
                    slot0.say(t51.u20)
                    return
            case "c":
                if bits >= 2500:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u25)
                        partner.add(offense=0)
                        partner.add(defense=5)
                        partner.add(speed=3)
                        partner.add(brain=0)
                        partner.add(max_hp=50)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=8)
                        partner.add(discipline=1)
                        partner.add(energy=35)
                        partner.add(weight=4)
                        take(bits=2500)
                        narrator.say(t51.u26)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u27)
                        return
                else:
                    slot0.say(t51.u24)
                    return
        slot0.say(t51.u28)
        return
    elif recruited(Species.Garurumon) and restaurant_chef == 2:
        slot0.say(t51.u2)
        match narrator.choose(a=t51.m2.o0, b=t51.m2.o1, c=t51.m2.o2):
            case "a":
                if bits >= 1000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u30)
                        partner.add(offense=0)
                        partner.add(defense=0)
                        partner.add(speed=0)
                        partner.add(brain=1)
                        partner.add(max_hp=10)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=0)
                        partner.add(discipline=1)
                        partner.add(energy=30)
                        partner.add(weight=3)
                        take(bits=1000)
                        narrator.say(t51.u31)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u32)
                        return
                else:
                    slot0.say(t51.u29)
                    return
            case "b":
                if bits >= 2500:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u34)
                        partner.add(offense=0)
                        partner.add(defense=0)
                        partner.add(speed=0)
                        partner.add(brain=2)
                        partner.add(max_hp=30)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=1)
                        partner.add(discipline=2)
                        partner.add(energy=40)
                        partner.add(weight=4)
                        take(bits=2500)
                        narrator.say(t51.u35)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u36)
                        return
                else:
                    slot0.say(t51.u33)
                    return
            case "c":
                if bits >= 5000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u38)
                        partner.add(offense=0)
                        partner.add(defense=0)
                        partner.add(speed=0)
                        partner.add(brain=3)
                        partner.add(max_hp=50)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=3)
                        partner.add(energy=50)
                        partner.add(weight=5)
                        take(bits=5000)
                        narrator.say(t51.u39)
                        partner.play(11, wait=True)
                    else:
                        partner.play(anim.refuse)
                        narrator.arrived()
                        slot0.say(t51.u40)
                        return
                else:
                    slot0.say(t51.u37)
                    return
        slot0.say(t51.u41)
        return
    match narrator.choose(a=t51.m0.o0, b=t51.m0.o1, c=t51.m0.o2):
        case "a":
            if bits >= 400:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u4)
                    partner.add(offense=1)
                    partner.add(defense=0)
                    partner.add(speed=0)
                    partner.add(brain=1)
                    partner.add(max_hp=0)
                    partner.add(max_mp=0)
                    partner.sub(tiredness=5)
                    partner.add(happiness=2)
                    partner.add(discipline=0)
                    partner.add(energy=20)
                    partner.add(weight=2)
                    take(bits=400)
                    narrator.say(t51.u5)
                    partner.play(11, wait=True)
                else:
                    partner.play(anim.refuse)
                    narrator.arrived()
                    slot0.say(t51.u6)
                    return
            else:
                slot0.say(t51.u3)
                return
        case "b":
            if bits >= 1200:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u8)
                    partner.add(offense=3)
                    partner.add(defense=0)
                    partner.add(speed=0)
                    partner.add(brain=2)
                    partner.add(max_hp=0)
                    partner.add(max_mp=0)
                    partner.sub(tiredness=5)
                    partner.add(happiness=4)
                    partner.add(discipline=0)
                    partner.add(energy=26)
                    partner.add(weight=3)
                    take(bits=1200)
                    narrator.say(t51.u9)
                    partner.play(11, wait=True)
                else:
                    partner.play(anim.refuse)
                    narrator.arrived()
                    slot0.say(t51.u10)
                    return
            else:
                slot0.say(t51.u7)
                return
        case "c":
            if bits >= 3500:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u12)
                    partner.add(offense=5)
                    partner.add(defense=0)
                    partner.add(speed=0)
                    partner.add(brain=3)
                    partner.add(max_hp=0)
                    partner.add(max_mp=0)
                    partner.sub(tiredness=5)
                    partner.add(happiness=6)
                    partner.add(discipline=1)
                    partner.add(energy=20)
                    partner.add(weight=4)
                    take(bits=3500)
                    narrator.say(t51.u13)
                    partner.play(11, wait=True)
                else:
                    partner.play(anim.refuse)
                    narrator.arrived()
                    slot0.say(t51.u14)
                    return
            else:
                slot0.say(t51.u11)
                return
    slot0.say(t51.u15)

# the section table, in the order of the original header
sections(254, 51)
