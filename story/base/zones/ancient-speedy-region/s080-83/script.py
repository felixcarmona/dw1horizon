# The Python view of script 80 of DG.SCN: screen 83 Ancient Speedy Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_speedy_region_83)
gotsumon0 = region.npc(Species.Gotsumon, slot=0)
gotsumon1 = region.npc(Species.Gotsumon, slot=1)
saberdramon = region.npc(Species.Saberdramon, slot=2)
darklizardmon3 = region.npc(Species.DarkLizardmon, slot=3)
darklizardmon4 = region.npc(Species.DarkLizardmon, slot=4)
gotsumon5 = region.npc(Species.Gotsumon, slot=5)
t10 = text.s080.sec10
t5 = text.s080.sec5
t51 = text.s080.sec51
t6 = text.s080.sec6
t7 = text.s080.sec7
t8 = text.s080.sec8
t9 = text.s080.sec9

@region.on_enter
def enter():    # section 254
    call(Routine.save_clock_speed, arg=1)

@gotsumon0.on_talk
def talk():    # section 5
    recruitable(gotsumon0, line=t5.u0)

@gotsumon1.on_talk
def talk():    # section 6
    recruitable(gotsumon1, line=t6.u0)

@saberdramon.on_talk
def talk():    # section 7
    recruitable(saberdramon, line=t7.u0)

@darklizardmon3.on_talk
def talk():    # section 8
    recruitable(darklizardmon3, line=t8.u0)

@darklizardmon4.on_talk
def talk():    # section 9
    recruitable(darklizardmon4, line=t9.u0)

@gotsumon5.on_talk
def talk():    # section 10
    recruitable(gotsumon5, line=t10.u0)

@region.on_step(0)
def step0():    # section 51
    if speedy_time_zone_entered:
        return
    tamer.play(24)
    wait(1000)
    tamer.say(t51.u0)
    tamer.play(anim.idle)
    tamer.say(t51.u1)
    speedy_time_zone_entered.set()
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7, 8, 9, 10, 51)
