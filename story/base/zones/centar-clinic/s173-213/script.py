# The Python view of script 173 of DG.SCN: screen 213 Centar Clinic.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text
from dw.names import *

clinic = screen(Screen.centar_clinic)
centarumon = clinic.npc(Species.Centarumon156, slot=0)
coelamon = clinic.npc(Species.Coelamon167, slot=1)
t6 = text.s173.sec6

@clinic.on_enter
def enter():    # section 254
    pass

@centarumon.on_talk
def talk():    # section 5
    jump_to_script(216, 51)

@coelamon.on_talk
def talk():    # section 6
    roll = random.roll(3)
    if roll == 0:
        say(t6.u0)
        return
    if roll == 1:
        say(t6.u1)
        return
    if roll == 2:
        say(t6.u2)
        return
    if roll == 3:
        say(t6.u3)
        return

@clinic.on_step(0)
def step0():    # section 51
    tamer.walk(1909, 860, wait=False)
    piximon_in_item_shop.clear()
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=5)
                    return
                warp(Screen.file_city_191, entry=5)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=5)
                return
            warp(Screen.file_city_190, entry=5)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=5)
                return
            warp(Screen.file_city_194, entry=5)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=5)
            return
        warp(Screen.file_city_189, entry=5)
        return
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=5)
                    return
                warp(Screen.file_city_183, entry=5)
                return
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=5)
                return
            warp(Screen.file_city_182, entry=5)
            return
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=5)
                return
            warp(Screen.file_city_186, entry=5)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=5)
            return
        warp(Screen.file_city_181, entry=5)
        return
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=5)
                return
            warp(Screen.file_city_198, entry=5)
            return
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=5)
            return
        warp(Screen.file_city_197, entry=5)
        return
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=5)
            return
        warp(Screen.file_city_201, entry=5)
        return
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=5)
        return
    warp(Screen.file_city_180, entry=5)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 51)
