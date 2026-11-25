# Overdell Cemetery 35: Bakemon, near where it was recruited in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_BAKEMON

site = screen(Screen.overdell_cemetery)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Bakemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
bakemon = site.npc(Species.Bakemon, at=(1350, 1350), bits=300, range=0, still=True, when=challenger == CH_BAKEMON, alone=challenger == CH_BAKEMON)



@bakemon.on_talk
def challenge_bakemon():
    if challenger != CH_BAKEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("bakemon.challenge.retry"))
        else:
            say(t("bakemon.challenge.intro1"), t("bakemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(bakemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("bakemon.challenge.won"))
                give(Item.TornTatter)
                give(bits=2500)
                narrator.say(t("bakemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1350, 3850)
                leave()
