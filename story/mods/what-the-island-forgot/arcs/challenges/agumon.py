# Native Forest 109: Agumon, recruited here in the original game; it works at the Item Keeper.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_AGUMON

site = screen(Screen.native_forest_109)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Agumon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
agumon = site.npc(Species.Agumon, at=(-250, 1700), bits=300, range=0, still=True, when=challenger == CH_AGUMON, alone=challenger == CH_AGUMON)



@agumon.on_talk
def challenge_agumon():
    if challenger != CH_AGUMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("agumon.challenge.retry"))
        else:
            say(t("agumon.challenge.intro1"), t("agumon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(agumon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("agumon.challenge.won"))
                give(Item.GreyClaws)
                give(bits=1500)
                narrator.say(t("agumon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-250, -800)
                leave()
