# The Python view of script 1 of DG.SCN: screen 0 Native Forest.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

forest = screen(Screen.native_forest_0)
modokibetamon0 = forest.npc(Species.ModokiBetamon, slot=0)
modokibetamon1 = forest.npc(Species.ModokiBetamon, slot=1)
redvegiemon2 = forest.npc(Species.RedVegiemon, slot=2)
redvegiemon3 = forest.npc(Species.RedVegiemon, slot=3)
modokibetamon4 = forest.npc(Species.ModokiBetamon, slot=4)
dokunemon5 = forest.npc(Species.Dokunemon, slot=5)
dokunemon6 = forest.npc(Species.Dokunemon, slot=6)
dokunemon7 = forest.npc(Species.Dokunemon, slot=7)
t10 = text.s001.sec10
t11 = text.s001.sec11
t12 = text.s001.sec12
t5 = text.s001.sec5
t6 = text.s001.sec6
t7 = text.s001.sec7
t8 = text.s001.sec8
t9 = text.s001.sec9

@forest.on_enter
def enter():    # section 254
    roll = random.roll(99)
    if roll <= 39:
        spawn_item(Item.Digimushrm, at=(2850, 1850))
    roll = random.roll(99)
    if roll <= 1:
        spawn_item(Item.Deluxmushrm, at=(-1050, 650))
    roll = random.roll(99)
    if roll <= 9:
        spawn_item(Item.Digimushrm, at=(-1450, -3850))
        spawn_item(Item.Digimushrm, at=(-1850, -3550))
        spawn_item(Item.Digimushrm, at=(-1950, -2950))
    roll = random.roll(99)
    if roll <= 14:
        spawn_item(Item.Digimushrm, at=(1850, -3450))
    roll = random.roll(99)
    if roll <= 24:
        spawn_item(Item.Digimushrm, at=(-50, 350))

@modokibetamon0.on_talk
def talk():    # section 5
    recruitable(modokibetamon0, line=t5.u0)

@modokibetamon1.on_talk
def talk():    # section 6
    recruitable(modokibetamon1, line=t6.u0)

@redvegiemon2.on_talk
def talk():    # section 7
    recruitable(redvegiemon2, line=t7.u0)

@redvegiemon3.on_talk
def talk():    # section 8
    recruitable(redvegiemon3, line=t8.u0)

@modokibetamon4.on_talk
def talk():    # section 9
    recruitable(modokibetamon4, line=t9.u0)

@dokunemon5.on_talk
def talk():    # section 10
    recruitable(dokunemon5, line=t10.u0)

@dokunemon6.on_talk
def talk():    # section 11
    recruitable(dokunemon6, line=t11.u0)

@dokunemon7.on_talk
def talk():    # section 12
    recruitable(dokunemon7, line=t12.u0)

@forest.on_step(0)
def step0():    # section 51
    if native_forest_rockslide_cleared:
        tamer.walk(-2315, 4000, wait=False)
        warp(Screen.native_forest_111, entry=3)
    tamer.walk(-2315, 4000, wait=False)
    warp(Screen.native_forest_110, entry=2)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 11, 12, 51)
