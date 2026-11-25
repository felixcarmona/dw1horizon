# 365, the Container House: the one real home of the Works. Starmon, fallen from Mt. Panorama's sky, and Bearmon, freed from the
# hunters' Kennel in the Seam (arcs/seam/kennel.py), share it.
from dw import *
from ..state import challenger, challenge_won, CH_STARMON

container_house = new_screen(365, map="build/what-the-island-forgot-maps/screens/BARR09.MAP")
starmon = container_house.npc(Species.Starmon, at=(-250, -450), range=0, when=recruited(Species.Starmon))
bearmon = container_house.npc(Species.Bearmon, at=(300, -200), range=0, when=recruited(Species.Bearmon))


# Resident challenges (content/tables/resident-challenges.json): the day it is out waiting at its old spot, it is not here.
@container_house.on_enter
def challenger_out():
    if challenger == CH_STARMON and not challenge_won:
        starmon.leave()


@starmon.on_talk
def talk():
    say("We painted the round window ourselves. From it I can almost see where I fell from.", "A box is a house once somebody waits for you in it.")


@bearmon.on_talk
def talk():
    say("I remember my name, I remember the hills. Every morning I say both out loud, just in case.")
