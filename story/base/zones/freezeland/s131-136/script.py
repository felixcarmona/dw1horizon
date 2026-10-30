# The Python view of script 131 of DG.SCN: screen 136 Freezeland.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.names import *

freezeland = screen(Screen.freezeland_136)

@freezeland.on_enter
def enter():    # section 254
    pass

@freezeland.on_step(0)
def step0():    # section 51
    if curling_match_pending == 0:
        return
    raw.call_digimon_routine(DigimonRoutine.curling)
    narrator.arrived()
    if not recruited(Species.Penguinmon):
        warp(Screen.freezeland_134, entry=2, then=10)
    else:
        warp(Screen.digimon_curling, entry=2, then=11)
    return

# the section table, in the order of the original header
sections(254, 51)
