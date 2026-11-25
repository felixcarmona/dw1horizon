# Misty Trees (screen 120, §3.1d): with the fog kept, the hunters cannot find the forest: its DarkLizardmon are not here.
from dw import *
from dw.base.misty_trees_120 import trees, darklizardmon
from ...state import fog_kept
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_GABUMON

@trees.on_enter(when=fog_kept)
def hidden_forest():
    darklizardmon.leave()


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Gabumon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home, at Treasure Hunt (city/treasure-hunt.py).
gabumon = trees.npc(Species.Gabumon, at=(-1050, 1250), bits=300, range=0, still=True, when=challenger == CH_GABUMON, alone=challenger == CH_GABUMON)



@gabumon.on_talk
def challenge_gabumon():
    if challenger != CH_GABUMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("gabumon.challenge.retry"))
        else:
            say(t("gabumon.challenge.intro1"), t("gabumon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(gabumon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("gabumon.challenge.won"))
                give(Item.WhiteFang)
                give(bits=1500)
                narrator.say(t("gabumon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1450, 1250)
                leave()
