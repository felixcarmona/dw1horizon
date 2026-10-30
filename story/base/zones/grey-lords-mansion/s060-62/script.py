# The Python view of script 60 of DG.SCN: screen 62 Grey Lord's Mansion.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

mansion = screen(Screen.grey_lords_mansion_62)
t82 = text.s060.sec82

@mansion.on_enter
def enter():    # section 254
    pass

@mansion.on_use(1)
def use1():    # section 81
    swing_door(0)
    sound(8, 1)
    wait(500)
    tamer.walk(1110, -2300, wait=False)
    warp(Screen.grey_lords_mansion_63, entry=1)

@mansion.on_use(2)
def use2():    # section 82
    tamer.say(t82.u0)
    objects[0].hide()
    objects[1].hide()
    objects[2].hide()
    objects[3].hide()
    objects[4].hide()
    objects[5].hide()
    objects[6].hide()
    objects[7].hide()
    objects[8].hide()
    objects[9].hide()
    objects[10].hide()
    objects[11].hide()
    objects[12].hide()
    objects[13].hide()
    objects[14].hide()
    objects[15].hide()
    objects[16].hide()
    objects[17].hide()
    objects[18].hide()
    objects[19].hide()
    objects[20].hide()
    objects[21].hide()
    objects[22].hide()
    objects[23].hide()
    objects[24].hide()
    objects[25].hide()
    objects[26].hide()
    objects[27].hide()
    objects[28].hide()
    objects[29].hide()
    objects[30].hide()
    objects[31].hide()
    objects[32].hide()
    objects[33].hide()
    objects[34].hide()
    objects[35].hide()
    objects[36].hide()
    objects[37].hide()
    objects[38].hide()
    objects[39].hide()
    objects[40].hide()
    objects[41].hide()
    objects[42].hide()
    objects[43].hide()
    objects[44].hide()
    objects[45].hide()
    objects[46].hide()
    objects[47].hide()
    objects[48].hide()
    objects[49].hide()
    objects[50].hide()
    objects[51].hide()
    objects[52].hide()
    objects[53].hide()
    objects[54].hide()
    objects[55].hide()
    objects[56].hide()
    objects[57].hide()
    objects[0].animate(57)
    sound(8, 7)
    wait(1750)
    tamer.walk(750, 0, wait=False)
    wait(500)
    warp(Screen.mansion_basement, entry=0)
    return

# the section table, in the order of the original header
sections(254, 81, 82)
