# Factorial Town 154: Megadramon, near where it was recruited in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MEGADRAMON

site = screen(Screen.factorial_town_154)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Megadramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
megadramon = site.npc(Species.Megadramon, at=(-550, 150), hp=5600, mp=4800, offense=660, defense=530, speed=510, brain=570, bits=300, range=0, still=True, when=challenger == CH_MEGADRAMON, alone=challenger == CH_MEGADRAMON)



@megadramon.on_talk
def challenge_megadramon():
    if challenger != CH_MEGADRAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("megadramon.challenge.retry"))
        else:
            say(t("megadramon.challenge.intro1"), t("megadramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(megadramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("megadramon.challenge.won"))
                give(Item.MegaHand)
                give(bits=4000)
                narrator.say(t("megadramon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1450, -1350)
                leave()
