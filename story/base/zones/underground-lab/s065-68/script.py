# The Python view of script 65 of DG.SCN: screen 68 Underground Lab.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

lab = screen(Screen.underground_lab_68)
tekkamon = lab.npc(Species.Tekkamon, slot=0)
darklizardmon1 = lab.npc(Species.DarkLizardmon, slot=1)
darklizardmon2 = lab.npc(Species.DarkLizardmon, slot=2)
darklizardmon3 = lab.npc(Species.DarkLizardmon, slot=3)
darklizardmon4 = lab.npc(Species.DarkLizardmon, slot=4)
darklizardmon5 = lab.npc(Species.DarkLizardmon, slot=5)
t10 = text.s065.sec10
t51 = text.s065.sec51
t6 = text.s065.sec6
t7 = text.s065.sec7
t8 = text.s065.sec8
t81 = text.s065.sec81
t9 = text.s065.sec9

@lab.on_enter
def enter():    # section 254
    pass

@lab.on_step(0)
def step0():    # section 51
    if not underground_lab_tekkamon_beaten:
        tekkamon.say(t51.u0)
        fight(tekkamon, escape=False)
        tekkamon.leave()
        underground_lab_tekkamon_beaten.set()
        recruit(Species.Tekkamon)
        camera.on(tamer, speed=10)
        camera.arrived()
        return

@lab.on_use(1)
def use1():    # section 81
    tamer.turn(2048)
    wait(250)
    tamer.say(t81.u0)

@tekkamon.on_talk
def talk():    # section 5
    return step0()

@darklizardmon1.on_talk
def talk():    # section 6
    recruitable(darklizardmon1, line=t6.u0)

@darklizardmon2.on_talk
def talk():    # section 7
    recruitable(darklizardmon2, line=t7.u0)

@darklizardmon3.on_talk
def talk():    # section 8
    recruitable(darklizardmon3, line=t8.u0)

@darklizardmon4.on_talk
def talk():    # section 9
    recruitable(darklizardmon4, line=t9.u0)

@darklizardmon5.on_talk
def talk():    # section 10
    recruitable(darklizardmon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 51, 81, 5, 6, 7, 8, 9, 10)
