# 358, the Courtyard: Clockmon, out of the Sewer, stands by the old well and keeps the Works' real time. Armadillomon, from the
# Ancient Speedy Region, looks for better things down the well (the Treasure Hunt 209 has no heap for its model).
from dw import *
from ..state import challenger, challenge_won, CH_ARMADILLOMON, CH_CLOCKMON

courtyard = new_screen(358, map="build/what-the-island-forgot-maps/screens/BARR02.MAP")
clockmon = courtyard.npc(Species.Clockmon, at=(-1700, 1000), range=0, when=recruited(Species.Clockmon))
armadillomon = courtyard.npc(Species.Armadillomon, at=(-1700, -2100), range=0, when=recruited(Species.Armadillomon))


# Resident challenges (content/tables/resident-challenges.json): the day it is out waiting at its old spot, it is not here.
@courtyard.on_enter
def challenger_out():
    if challenger == CH_ARMADILLOMON and not challenge_won:
        armadillomon.leave()
    if challenger == CH_CLOCKMON and not challenge_won:
        clockmon.leave()


@clockmon.on_talk
def talk():
    if clock.hour >= 11 and clock.hour <= 13:
        say("Tick. Tock. Twelve, and this time it is true.")
    else:
        say("Tick. Tock. It stopped being twelve, and I am so glad.", "A city needs a real clock.")


@armadillomon.on_talk
def talk():
    say("Treasure! I swear there's treasure somewhere under this city!", "This old well goes down a long way. I'm only checking.")
