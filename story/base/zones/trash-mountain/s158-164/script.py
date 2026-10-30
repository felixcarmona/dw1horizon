# The Python view of script 158 of DG.SCN: screen 164 Trash Mountain.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

mountain = screen(Screen.trash_mountain_164)
psychemon0 = mountain.npc(Species.Psychemon, slot=0)
geremon1 = mountain.npc(Species.Geremon, slot=1)
geremon2 = mountain.npc(Species.Geremon, slot=2)
geremon3 = mountain.npc(Species.Geremon, slot=3)
psychemon4 = mountain.npc(Species.Psychemon, slot=4)
psychemon5 = mountain.npc(Species.Psychemon, slot=5)
t10 = text.s158.sec10
t5 = text.s158.sec5
t6 = text.s158.sec6
t7 = text.s158.sec7
t8 = text.s158.sec8
t9 = text.s158.sec9

@mountain.on_enter
def enter():    # section 254
    if clock.hour >= 7 and clock.hour < 19:
        return
    objects[19].hide()
    objects[20].hide()
    objects[21].hide()
    objects[22].hide()

@psychemon0.on_talk
def talk():    # section 5
    recruitable(psychemon0, line=t5.u0)

@geremon1.on_talk
def talk():    # section 6
    recruitable(geremon1, line=t6.u0)

@geremon2.on_talk
def talk():    # section 7
    recruitable(geremon2, line=t7.u0)

@geremon3.on_talk
def talk():    # section 8
    recruitable(geremon3, line=t8.u0)

@psychemon4.on_talk
def talk():    # section 9
    recruitable(psychemon4, line=t9.u0)

@psychemon5.on_talk
def talk():    # section 10
    recruitable(psychemon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
