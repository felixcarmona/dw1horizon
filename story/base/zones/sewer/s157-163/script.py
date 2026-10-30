# The Python view of script 157 of DG.SCN: screen 163 Sewer.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *

sewer = screen(Screen.sewer_163)

@sewer.on_enter
def enter():    # section 254
    pass

@sewer.on_step(0)
def step0():    # section 51
    tamer.walk(877, -652, wait=False)
    tamer.walk(1962, -1388, wait=False)
    warp(Screen.sewer_220, entry=0)

@sewer.on_step(1)
def step1():    # section 52
    warp(Screen.factorial_town_154, entry=1)
    return

# the section table, in the order of the original header
sections(254, 51, 52)
