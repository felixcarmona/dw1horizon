# 357, the Stone Yard: the Works' first outdoor screen (design/district-proposals.md, concept 3), a file of its own
# because its stairs run a script.
from dw import *

stone_yard = new_screen(357, map="build/what-the-island-forgot-maps/screens/BARR01.MAP")
# the resident: Digmon by the stairs (the Drill Tunnel), standing here once beaten where it lived
digmon = stone_yard.npc(Species.Digmon, at=(-1200, -2000), range=0, when=recruited(Species.Digmon))


@digmon.on_talk
def talk():
    say("Every stone of this yard I set myself.", "In the tunnels nobody came back to thank me. Here you all walk on it.")


# The Stone Yard's stairs (its tiles run step 0) go down to the gate in the lower town's hedge (maps/twnb-gate.py: exit 7
# of every TWNB screen). The lower town is one of 24 screens, one per stage of the city's growth, and the screen you leave
# from picks it: the same tree as the Native Forest's exit (base s105, section 51), arriving at exit 7.
@stone_yard.on_step(0)
def to_lower_town():
    if recruited(Species.Patamon) or recruited(Species.Biyomon) or recruited(Species.Unimon) or recruited(Species.Monochromon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_192, entry=7)
                warp(Screen.file_city_191, entry=7)
            if recruited(Species.Greymon):
                warp(Screen.file_city_193, entry=7)
            warp(Screen.file_city_190, entry=7)
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_195, entry=7)
            warp(Screen.file_city_194, entry=7)
        if recruited(Species.Greymon):
            warp(Screen.file_city_196, entry=7)
        warp(Screen.file_city_189, entry=7)
    if recruited(Species.Betamon) or recruited(Species.Coelamon):
        if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
            if recruited(Species.Centarumon):
                if recruited(Species.Greymon):
                    warp(Screen.file_city_184, entry=7)
                warp(Screen.file_city_183, entry=7)
            if recruited(Species.Greymon):
                warp(Screen.file_city_185, entry=7)
            warp(Screen.file_city_182, entry=7)
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_187, entry=7)
            warp(Screen.file_city_186, entry=7)
        if recruited(Species.Greymon):
            warp(Screen.file_city_188, entry=7)
        warp(Screen.file_city_181, entry=7)
    if recruited(Species.Meramon) or recruited(Species.Tyrannomon) or recruited(Species.Garurumon) or recruited(Species.Frigimon):
        if recruited(Species.Centarumon):
            if recruited(Species.Greymon):
                warp(Screen.file_city_199, entry=7)
            warp(Screen.file_city_198, entry=7)
        if recruited(Species.Greymon):
            warp(Screen.file_city_200, entry=7)
        warp(Screen.file_city_197, entry=7)
    if recruited(Species.Centarumon):
        if recruited(Species.Greymon):
            warp(Screen.file_city_202, entry=7)
        warp(Screen.file_city_201, entry=7)
    if recruited(Species.Greymon):
        warp(Screen.file_city_203, entry=7)
    warp(Screen.file_city_180, entry=7)
