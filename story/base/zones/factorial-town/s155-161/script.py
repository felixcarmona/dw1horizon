# The Python view of script 155 of DG.SCN: screen 161 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

town = screen(Screen.factorial_town_161)
guardromon0 = town.npc(Species.Guardromon, slot=0)
platinumsukamon = town.npc(Species.PlatinumSukamon, slot=1)
guardromon2 = town.npc(Species.Guardromon, slot=2)
geremon3 = town.npc(Species.Geremon, slot=3)
geremon4 = town.npc(Species.Geremon, slot=4)
geremon5 = town.npc(Species.Geremon, slot=5)
t10 = text.s155.sec10
t5 = text.s155.sec5
t6 = text.s155.sec6
t7 = text.s155.sec7
t8 = text.s155.sec8
t9 = text.s155.sec9

@town.on_enter
def enter():    # section 254
    factory_guards_passed.set()
    spawn_chest(Item.HPChip, at=(-2886, -683), opened=trigger(677), facing=2048)
    spawn_chest(Item.MPChip, at=(-3672, -683), opened=trigger(678), facing=2048)

@guardromon0.on_talk
def talk():    # section 5
    recruitable(guardromon0, line=t5.u0)

@platinumsukamon.on_talk
def talk():    # section 6
    recruitable(platinumsukamon, line=t6.u0)

@guardromon2.on_talk
def talk():    # section 7
    recruitable(guardromon2, line=t7.u0)

@geremon3.on_talk
def talk():    # section 8
    recruitable(geremon3, line=t8.u0)

@geremon4.on_talk
def talk():    # section 9
    recruitable(geremon4, line=t9.u0)

@geremon5.on_talk
def talk():    # section 10
    recruitable(geremon5, line=t10.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10)
