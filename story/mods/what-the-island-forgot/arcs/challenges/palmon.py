# Native Forest 4, next to Native Forest 2 where it was recruited in the original game (screen 2 has no heap left for it beside the night hunter); it lives in the city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_PALMON

site = screen(Screen.native_forest_4)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Palmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
palmon = site.npc(Species.Palmon, at=(2650, -500), hp=590, mp=610, offense=120, defense=90, speed=100, brain=80, bits=300, range=0, still=True, when=challenger == CH_PALMON, alone=challenger == CH_PALMON)



@palmon.on_talk
def challenge_palmon():
    if challenger != CH_PALMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("palmon.challenge.retry"))
        else:
            say(t("palmon.challenge.intro1"), t("palmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(palmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("palmon.challenge.won"))
                give(Item.Digipine)
                give(bits=1500)
                narrator.say(t("palmon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(3100, -100)
                leave()
