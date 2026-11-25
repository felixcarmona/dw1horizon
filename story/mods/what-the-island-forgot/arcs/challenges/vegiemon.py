# Tropical Jungle 14: Vegiemon, recruited here in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_VEGIEMON

site = screen(Screen.tropical_jungle_14)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Vegiemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
vegiemon = site.npc(Species.Vegiemon, at=(-1050, -2250), bits=300, range=0, still=True, when=challenger == CH_VEGIEMON, alone=challenger == CH_VEGIEMON)



@vegiemon.on_talk
def challenge_vegiemon():
    if challenger != CH_VEGIEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("vegiemon.challenge.retry"))
        else:
            say(t("vegiemon.challenge.intro1"), t("vegiemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(vegiemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("vegiemon.challenge.won"))
                give(Item.Fertilizer)
                give(bits=2500)
                narrator.say(t("vegiemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1450, -2250)
                leave()
