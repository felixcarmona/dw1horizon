# Factorial Town 153: MetalMamemon, recruited here in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_METALMAMEMON

site = screen(Screen.factorial_town_153)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day MetalMamemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
metalmamemon = site.npc(Species.MetalMamemon, at=(-1700, -100), bits=300, range=0, still=True, when=challenger == CH_METALMAMEMON, alone=challenger == CH_METALMAMEMON)



@metalmamemon.on_talk
def challenge_metalmamemon():
    if challenger != CH_METALMAMEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("metalmamemon.challenge.retry"))
        else:
            say(t("metalmamemon.challenge.intro1"), t("metalmamemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(metalmamemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("metalmamemon.challenge.won"))
                give(Item.MetalArmor)
                give(bits=4000)
                narrator.say(t("metalmamemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-3700, 1400)
                leave()
