# Digimon Bridge 9: Ninjamon, recruited here in the original game; it lives in the city (city/secret-item-shop.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_NINJAMON

site = screen(Screen.digimon_bridge_9)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Ninjamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
ninjamon = site.npc(Species.Ninjamon, at=(-900, -1100), hp=3800, mp=3500, offense=620, defense=210, speed=350, brain=250, bits=300, range=0, still=True, when=challenger == CH_NINJAMON, alone=challenger == CH_NINJAMON)



@ninjamon.on_talk
def challenge_ninjamon():
    if challenger != CH_NINJAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("ninjamon.challenge.retry"))
        else:
            say(t("ninjamon.challenge.intro1"), t("ninjamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(ninjamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("ninjamon.challenge.won"))
                give(Item.KogaLaws)
                give(bits=2500)
                narrator.say(t("ninjamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-900, 1400)
                leave()
