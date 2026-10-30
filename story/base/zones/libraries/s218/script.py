# The Python view of script 218 of DG.SCN (no screen loads it).
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lib = script(218)
slot0 = lib.npc(None, slot=0)    # no NPC of the .MAP in this slot; the script spawns what stands here
t51 = text.s218.sec51

@lib.on_enter
def enter():    # section 254
    pass

@lib.on_step(0)
def step0():    # section 51
    if recruited(Species.Frigimon) and restaurant_chef == 3:
        slot0.say(t51.u0)
    elif recruited(Species.Vademon) and restaurant_chef == 4:
        slot0.say(t51.u1)
        match narrator.choose(a=t51.m1.o0, b=t51.m1.o1, c=t51.m1.o2):
            case "a":
                if bits >= 1500:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u17)
                        partner.add(offense=1)
                        partner.add(defense=1)
                        partner.add(speed=1)
                        partner.add(brain=1)
                        partner.add(max_hp=10)
                        partner.add(max_mp=10)
                        partner.sub(tiredness=5)
                        partner.add(happiness=1)
                        partner.add(discipline=1)
                        partner.add(energy=20)
                        partner.add(weight=0)
                        take(bits=1500)
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
                if bits >= 4000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u21)
                        partner.add(offense=2)
                        partner.add(defense=2)
                        partner.add(speed=2)
                        partner.add(brain=2)
                        partner.add(max_hp=20)
                        partner.add(max_mp=20)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=2)
                        partner.add(energy=30)
                        partner.add(weight=1)
                        take(bits=4000)
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
                if bits >= 9000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u25)
                        partner.add(offense=3)
                        partner.add(defense=3)
                        partner.add(speed=3)
                        partner.add(brain=3)
                        partner.add(max_hp=30)
                        partner.add(max_mp=30)
                        partner.sub(tiredness=5)
                        partner.add(happiness=3)
                        partner.add(discipline=3)
                        partner.add(energy=45)
                        partner.add(weight=5)
                        take(bits=9000)
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
    elif recruited(Species.Digitamamon) and restaurant_chef == 5:
        slot0.say(t51.u2)
        match narrator.choose(a=t51.m2.o0, b=t51.m2.o1, c=t51.m2.o2):
            case "a":
                if bits >= 1000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u30)
                        roll = random.roll(2)
                    if roll <= 0:
                        partner.add(offense=1)
                        partner.add(defense=0)
                        partner.add(speed=1)
                        partner.add(brain=0)
                        partner.add(max_hp=10)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=1)
                        partner.add(discipline=0)
                        partner.add(energy=18)
                        partner.add(weight=1)
                        take(bits=1000)
                        narrator.say(t51.u31)
                        narrator.say(t51.u32)
                    elif roll <= 1:
                        partner.add(offense=0)
                        partner.add(defense=1)
                        partner.add(speed=0)
                        partner.add(brain=1)
                        partner.add(max_hp=0)
                        partner.add(max_mp=10)
                        partner.sub(tiredness=5)
                        partner.add(happiness=1)
                        partner.add(discipline=0)
                        partner.add(energy=18)
                        partner.add(weight=1)
                        take(bits=1000)
                        narrator.say(t51.u33)
                        narrator.say(t51.u34)
                    elif roll <= 2:
                        partner.add(offense=2)
                        partner.add(defense=2)
                        partner.add(speed=2)
                        partner.add(brain=2)
                        partner.add(max_hp=20)
                        partner.add(max_mp=20)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=1)
                        partner.add(energy=18)
                        partner.add(weight=1)
                        take(bits=1000)
                        narrator.say(t51.u35)
                        narrator.say(t51.u36)
                    else:
                        partner.play(11, wait=True)
                else:
                    slot0.say(t51.u29)
                    return
            case "b":
                if bits >= 2500:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u39)
                        roll = random.roll(2)
                    if roll <= 0:
                        partner.add(offense=2)
                        partner.add(defense=0)
                        partner.add(speed=2)
                        partner.add(brain=0)
                        partner.add(max_hp=20)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=0)
                        partner.add(energy=24)
                        partner.add(weight=2)
                        take(bits=2500)
                        narrator.say(t51.u40)
                        narrator.say(t51.u41)
                    elif roll <= 1:
                        partner.add(offense=0)
                        partner.add(defense=2)
                        partner.add(speed=0)
                        partner.add(brain=2)
                        partner.add(max_hp=0)
                        partner.add(max_mp=20)
                        partner.sub(tiredness=5)
                        partner.add(happiness=2)
                        partner.add(discipline=0)
                        partner.add(energy=24)
                        partner.add(weight=2)
                        take(bits=2500)
                        narrator.say(t51.u42)
                        narrator.say(t51.u43)
                    elif roll <= 2:
                        partner.add(offense=3)
                        partner.add(defense=3)
                        partner.add(speed=3)
                        partner.add(brain=3)
                        partner.add(max_hp=30)
                        partner.add(max_mp=30)
                        partner.sub(tiredness=5)
                        partner.add(happiness=3)
                        partner.add(discipline=1)
                        partner.add(energy=24)
                        partner.add(weight=2)
                        take(bits=2500)
                        narrator.say(t51.u44)
                        narrator.say(t51.u45)
                    else:
                        partner.play(11, wait=True)
                else:
                    slot0.say(t51.u38)
                    return
            case "c":
                if bits >= 6000:
                    if not partner_energy_full or partner.hungry:
                        narrator.say(t51.u48)
                        roll = random.roll(2)
                    if roll <= 0:
                        partner.add(offense=3)
                        partner.add(defense=0)
                        partner.add(speed=3)
                        partner.add(brain=0)
                        partner.add(max_hp=30)
                        partner.add(max_mp=0)
                        partner.sub(tiredness=5)
                        partner.add(happiness=3)
                        partner.add(discipline=1)
                        partner.add(energy=36)
                        partner.add(weight=3)
                        take(bits=6000)
                        narrator.say(t51.u49)
                        narrator.say(t51.u50)
                    elif roll <= 1:
                        partner.add(offense=0)
                        partner.add(defense=3)
                        partner.add(speed=0)
                        partner.add(brain=3)
                        partner.add(max_hp=0)
                        partner.add(max_mp=30)
                        partner.sub(tiredness=5)
                        partner.add(happiness=3)
                        partner.add(discipline=1)
                        partner.add(energy=36)
                        partner.add(weight=3)
                        take(bits=6000)
                        narrator.say(t51.u51)
                        narrator.say(t51.u52)
                    elif roll <= 2:
                        partner.add(offense=4)
                        partner.add(defense=4)
                        partner.add(speed=4)
                        partner.add(brain=4)
                        partner.add(max_hp=40)
                        partner.add(max_mp=40)
                        partner.sub(tiredness=5)
                        partner.add(happiness=4)
                        partner.add(discipline=3)
                        partner.add(energy=36)
                        partner.add(weight=3)
                        take(bits=6000)
                        narrator.say(t51.u53)
                        narrator.say(t51.u54)
                    else:
                        partner.play(11, wait=True)
                else:
                    slot0.say(t51.u47)
                    return
        slot0.say(t51.u56)
        return
    match narrator.choose(a=t51.m0.o0, b=t51.m0.o1, c=t51.m0.o2):
        case "a":
            if bits >= 300:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u4)
                    partner.add(offense=0)
                    partner.add(defense=0)
                    partner.add(speed=1)
                    partner.add(brain=0)
                    partner.add(max_hp=0)
                    partner.add(max_mp=10)
                    partner.sub(tiredness=2)
                    partner.add(happiness=3)
                    partner.add(discipline=0)
                    partner.add(energy=12)
                    partner.add(weight=2)
                    take(bits=300)
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
            if bits >= 700:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u8)
                    partner.add(offense=0)
                    partner.add(defense=0)
                    partner.add(speed=2)
                    partner.add(brain=0)
                    partner.add(max_hp=0)
                    partner.add(max_mp=30)
                    partner.sub(tiredness=2)
                    partner.add(happiness=5)
                    partner.add(discipline=0)
                    partner.add(energy=16)
                    partner.add(weight=3)
                    take(bits=700)
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
            if bits >= 1600:
                if not partner_energy_full or partner.hungry:
                    narrator.say(t51.u12)
                    partner.add(offense=0)
                    partner.add(defense=0)
                    partner.add(speed=2)
                    partner.add(brain=0)
                    partner.add(max_hp=0)
                    partner.add(max_mp=50)
                    partner.sub(tiredness=2)
                    partner.add(happiness=7)
                    partner.add(discipline=1)
                    partner.add(energy=20)
                    partner.add(weight=4)
                    take(bits=1600)
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
