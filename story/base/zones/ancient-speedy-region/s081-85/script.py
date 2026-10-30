# The Python view of script 81 of DG.SCN: screen 85 Ancient Speedy Region.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

region = screen(Screen.ancient_speedy_region_85)
saberdramon = region.npc(Species.Saberdramon, slot=0)
t5 = text.s081.sec5

@region.on_enter
def enter():    # section 254
    saberdramon_fought_this_visit.clear()

@saberdramon.on_talk
def talk():    # section 5
    if not saberdramon_fought_this_visit:
        say(t5.u0)
        engine.no_escape.set()
        fight()
        recruit(Species.Saberdramon)
        engine.no_escape.clear()
        saberdramon_fought_this_visit.set()
        walk(-554, -1006)
    say(t5.u1)
    camera.on(tamer, speed=10)
    camera.arrived()
    return

# the section table, in the order of the original header
sections(254, 5)
