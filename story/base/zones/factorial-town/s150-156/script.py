# The Python view of script 150 of DG.SCN: screen 156 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.names import *

town = screen(Screen.factorial_town_156)

@town.on_enter
def enter():    # section 254
    if not factorial_town_reopened:
        raw.set_rect_impassable(0, 75, 67, 20, 8)
        return
    objects[0].show()
    objects[1].show()
    objects[2].hide()
    objects[3].hide()
    objects[4].hide()

@town.on_step(0)
def step0():    # section 51
    return

# the section table, in the order of the original header
sections(254, 51)
