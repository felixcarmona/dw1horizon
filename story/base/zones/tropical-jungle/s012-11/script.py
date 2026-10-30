# The Python view of script 12 of DG.SCN: screen 11 Tropical Jungle.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

jungle = screen(Screen.tropical_jungle_11)
aruraumon0 = jungle.npc(Species.Aruraumon, slot=0)
aruraumon1 = jungle.npc(Species.Aruraumon, slot=1)
tsukaimon2 = jungle.npc(Species.Tsukaimon, slot=2)
tsukaimon3 = jungle.npc(Species.Tsukaimon, slot=3)
t5 = text.s012.sec5
t53 = text.s012.sec53
t6 = text.s012.sec6
t7 = text.s012.sec7
t8 = text.s012.sec8
t81 = text.s012.sec81

@jungle.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(550, 650))
    roll = random.roll(99)
    if roll <= 4:
        spawn_item(Item.Digimushrm, at=(1850, 350))

@jungle.on_use(1)
def use1():    # section 81
    narrator.say(t81.u0)
    tamer.turn(2048)
    tamer.say(t81.u1)
    match choose(a=t81.m0.o0, b=t81.m0.o1, c=t81.m0.o2):
        case "a":
            if bits >= 200:
                partner.add(mp=100)
                take(bits=200)
                narrator.say(t81.u2)
            else:
                tamer.say(t81.u3)
                return
            return
        case "b":
            if bits >= 1800:
                partner.add(mp=1000)
                take(bits=1800)
                narrator.say(t81.u4)
            else:
                tamer.say(t81.u5)
                return
            return
    tamer.say(t81.u6)

@jungle.on_step(2)
def step2():    # section 53
    if eastern_bridge_seen:
        return
    tamer.say(t53.u0)
    eastern_bridge_seen.set()

@aruraumon0.on_talk
def talk():    # section 5
    recruitable(aruraumon0, line=t5.u0)

@aruraumon1.on_talk
def talk():    # section 6
    recruitable(aruraumon1, line=t6.u0)

@tsukaimon2.on_talk
def talk():    # section 7
    recruitable(tsukaimon2, line=t7.u0)

@tsukaimon3.on_talk
def talk():    # section 8
    recruitable(tsukaimon3, line=t8.u0)
    return

# the section table, in the order of the original header
sections(254, 81, 53, 5, 6, 7, 8)
