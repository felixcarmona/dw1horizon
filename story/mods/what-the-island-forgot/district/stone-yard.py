# 357, the Stone Yard: the Works' first outdoor screen (design/district-proposals.md, concept 3), a file of its own
# because its stairs run a script.
from dw import *

stone_yard = new_screen(357, map="build/what-the-island-forgot-maps/screens/BARR01.MAP")
# the residents: Golemon by the stairs (Mt. Infinity), MoriShellmon on the left (Misty Trees), Saberdramon on the
# right of the stairs (the Ancient Speedy Region), each standing here once beaten where it lived
golemon = stone_yard.npc(Species.Golemon, at=(-1200, -2000), range=0, when=recruited(Species.Golemon))
morishellmon = stone_yard.npc(Species.MoriShellmon, at=(-1500, -1000), range=0, when=recruited(Species.MoriShellmon))
saberdramon = stone_yard.npc(Species.Saberdramon, at=(1300, -2100), range=0, when=recruited(Species.Saberdramon))


@golemon.on_talk
def talk():
    say("Every stone of this yard I set myself.", "Mt. Infinity has too many stones and nobody to set them.")


@morishellmon.on_talk
def talk():
    say("Heh heh... this old fella has seen the island forget a lot of things.",
        "Sit a while. The Works remember better than the forest did.")


@saberdramon.on_talk
def talk():
    if clock.hour >= 20 or clock.hour < 5:
        say("At night I fly over the hedge and count the lights of the city. More every week.")
    else:
        say("Kraah! The fastest wings in the Speedy Region, and you still caught me.")


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
