# Kunemon's Bed 1: Kunemon, recruited here in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KUNEMON

site = screen(Screen.kunemons_bed)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kunemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kunemon = site.npc(Species.Kunemon, at=(-50, -800), hp=590, mp=610, offense=120, defense=90, speed=100, brain=80, bits=300, range=0, still=True, when=challenger == CH_KUNEMON, alone=challenger == CH_KUNEMON)



@kunemon.on_talk
def challenge_kunemon():
    if challenger != CH_KUNEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kunemon.challenge.retry"))
        else:
            say(t("kunemon.challenge.intro1"), t("kunemon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kunemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kunemon.challenge.won"))
                give(Item.CalmBerry)
                give(bits=1500)
                narrator.say(t("kunemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1450, 1200)
                leave()
