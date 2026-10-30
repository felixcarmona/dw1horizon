# The Python view of script 11 of DG.SCN: screen 10 Digimon Bridge.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

bridge = screen(Screen.digimon_bridge_10)
modokibetamon0 = bridge.npc(Species.ModokiBetamon, slot=0)
modokibetamon1 = bridge.npc(Species.ModokiBetamon, slot=1)
aruraumon = bridge.npc(Species.Aruraumon, slot=2)
tsukaimon3 = bridge.npc(Species.Tsukaimon, slot=3)
tsukaimon4 = bridge.npc(Species.Tsukaimon, slot=4)
tsukaimon5 = bridge.npc(Species.Tsukaimon, slot=5)
t10 = text.s011.sec10
t5 = text.s011.sec5
t6 = text.s011.sec6
t7 = text.s011.sec7
t8 = text.s011.sec8
t9 = text.s011.sec9

@bridge.on_enter
def enter():    # section 254
    if recruited(Species.Kunemon):
        objects[68].show()
        objects[69].show()
        objects[70].show()
    else:
        raw.set_rect_impassable(0, 22, 16, 3, 12)
    if recruited(Species.Kunemon) and engine.prosperity >= 35:
        objects[71].hide()
        objects[72].hide()
        objects[73].hide()
    roll = random.roll(99)
    if roll <= 39:
        spawn_item(Item.Digimushrm, at=(-1250, 150))
    roll = random.roll(99)
    if roll <= 3:
        spawn_item(Item.BlueApple, at=(-1150, -250))

@modokibetamon0.on_talk
def talk():    # section 5
    recruitable(modokibetamon0, line=t5.u0)

@aruraumon.on_talk
def talk():    # section 7
    recruitable(aruraumon, line=t7.u0)

@tsukaimon3.on_talk
def talk():    # section 8
    recruitable(tsukaimon3, line=t8.u0)

@tsukaimon4.on_talk
def talk():    # section 9
    recruitable(tsukaimon4, line=t9.u0)

@tsukaimon5.on_talk
def talk():    # section 10
    recruitable(tsukaimon5, line=t10.u0)

@modokibetamon1.on_talk
def talk():    # section 6
    recruitable(modokibetamon1, line=t6.u0)

@bridge.on_step(1)
def step1():    # section 52
    tamer.walk(-2800, 3000, wait=False)
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=2)
                    return
                warp(Screen.file_city_191, entry=2)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=2)
                return
            warp(Screen.file_city_190, entry=2)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=2)
                return
            warp(Screen.file_city_194, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=2)
            return
        warp(Screen.file_city_189, entry=2)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=2)
                    return
                warp(Screen.file_city_183, entry=2)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=2)
                return
            warp(Screen.file_city_182, entry=2)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=2)
                return
            warp(Screen.file_city_186, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=2)
            return
        warp(Screen.file_city_181, entry=2)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=2)
                return
            warp(Screen.file_city_198, entry=2)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=2)
            return
        warp(Screen.file_city_197, entry=2)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=2)
            return
        warp(Screen.file_city_201, entry=2)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=2)
        return
    warp(Screen.file_city_180, entry=2)
    return

# the section table, in the order of the original header
sections(254, 5, 7, 8, 9, 10, 6, 52)
