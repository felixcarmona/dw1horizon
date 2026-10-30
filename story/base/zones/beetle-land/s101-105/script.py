# The Python view of script 101 of DG.SCN: screen 105 Beetle Land.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

land = screen(Screen.beetle_land_105)
tentomon0 = land.npc(Species.Tentomon, slot=0)
tentomon1 = land.npc(Species.Tentomon, slot=1)
tentomon2 = land.npc(Species.Tentomon, slot=2)
dokunemon3 = land.npc(Species.Dokunemon, slot=3)
dokunemon4 = land.npc(Species.Dokunemon, slot=4)
dokunemon5 = land.npc(Species.Dokunemon, slot=5)
tentomon6 = land.npc(Species.Tentomon, slot=6)
tentomon7 = land.npc(Species.Tentomon, slot=7)
t10 = text.s101.sec10
t11 = text.s101.sec11
t12 = text.s101.sec12
t5 = text.s101.sec5
t6 = text.s101.sec6
t7 = text.s101.sec7
t8 = text.s101.sec8
t81 = text.s101.sec81
t9 = text.s101.sec9

@land.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.GoldAcorn, at=(-1350, -1950))

@land.on_use(1)
def use1():    # section 81
    if not has(Item.BlueFlute):
        return
    narrator.say(t81.u0)
    match choose(a=t81.m0.o0, b=t81.m0.o1):
        case "a":
            wait(3000)
            warp(Screen.dragon_eye_lake_6, entry=0)
            return step0()
        case "b":
            return
        case _:
            return

@land.on_step(0)
def step0():    # section 51
    tamer.walk(-1061, -331, wait=False)
    warp(Screen.factorial_town_154, entry=3)

@tentomon0.on_talk
def talk():    # section 5
    recruitable(tentomon0, line=t5.u0)

@tentomon1.on_talk
def talk():    # section 6
    recruitable(tentomon1, line=t6.u0)

@tentomon2.on_talk
def talk():    # section 7
    recruitable(tentomon2, line=t7.u0)

@dokunemon3.on_talk
def talk():    # section 8
    recruitable(dokunemon3, line=t8.u0)

@dokunemon4.on_talk
def talk():    # section 9
    recruitable(dokunemon4, line=t9.u0)

@dokunemon5.on_talk
def talk():    # section 10
    recruitable(dokunemon5, line=t10.u0)

@tentomon6.on_talk
def talk():    # section 11
    dokunemon4.say(t11.u0)
    fight()
    recruit(Species.Tentomon)

@tentomon7.on_talk
def talk():    # section 12
    dokunemon5.say(t12.u0)
    fight()
    recruit(Species.Tentomon)
    return

# the section table, in the order of the original header
sections(254, 81, 51, 5, 6, 7, 8, 9, 10, 11, 12)
