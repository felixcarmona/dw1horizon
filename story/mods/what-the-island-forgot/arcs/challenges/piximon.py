# Tropical Jungle 12: Piximon, recruited here in the original game; it lives in the city (city/item-shop.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_PIXIMON

site = screen(Screen.tropical_jungle_12)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Piximon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
piximon = site.npc(Species.Piximon, at=(-750, -1250), hp=5200, mp=4600, offense=680, defense=460, speed=660, brain=600, bits=300, range=0, still=True, when=challenger == CH_PIXIMON, alone=challenger == CH_PIXIMON)



@piximon.on_talk
def challenge_piximon():
    if challenger != CH_PIXIMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("piximon.challenge.retry"))
        else:
            say(t("piximon.challenge.intro1"), t("piximon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(piximon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("piximon.challenge.won"))
                give(Item.SmallSpear)
                give(bits=4000)
                narrator.say(t("piximon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1650, -1950)
                leave()
