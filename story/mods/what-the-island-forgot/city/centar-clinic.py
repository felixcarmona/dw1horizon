# The Clinic (213): Mushroomon (Mt. Panorama's Spore Area) sells herbs and medicine by the stools, clear of the door (arrival
# at (1078, 786)).
from dw import *
from dw.base.centar_clinic import clinic, coelamon
from ..state import challenger, challenge_won, CH_MUSHROOMON

mushroomon = clinic.npc(Species.Mushroomon, at=(50, 1150), behaves_like=coelamon, when=recruited(Species.Mushroomon))


# Resident challenges (content/tables/resident-challenges.json): the day it is out waiting at its old spot, it is not here.
@clinic.on_enter(when=engine.game_beaten)
def challenger_out():
    if challenger == CH_MUSHROOMON and not challenge_won:
        mushroomon.leave()


@mushroomon.on_talk
def talk():
    say("Ah-choo! Excuse me. On the mountain my spores made everyone sick.", "Here Centarumon lets me sell the cure.")
    shop(Item.Bandage, Item.Medicine, Item.SmRecovery, Item.MPFloppy)
