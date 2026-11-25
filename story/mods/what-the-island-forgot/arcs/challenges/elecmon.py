# Gear Savanna 71: Elecmon, recruited here in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_ELECMON

site = screen(Screen.gear_savanna_71)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Elecmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
elecmon = site.npc(Species.Elecmon, at=(-150, -400), bits=300, range=0, still=True, when=challenger == CH_ELECMON, alone=challenger == CH_ELECMON)



@elecmon.on_talk
def challenge_elecmon():
    if challenger != CH_ELECMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("elecmon.challenge.retry"))
        else:
            say(t("elecmon.challenge.intro1"), t("elecmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(elecmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("elecmon.challenge.won"))
                give(Item.ElectoRing)
                give(bits=1500)
                narrator.say(t("elecmon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-150, 2100)
                leave()
