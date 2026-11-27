# Native Forest 3: Etemon, recruited here in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_ETEMON

site = screen(Screen.native_forest_3)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Etemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
etemon = site.npc(Species.Etemon, at=(300, 1850), hp=5600, mp=5600, offense=700, defense=580, speed=530, brain=600, bits=300, range=0, still=True, when=challenger == CH_ETEMON, alone=challenger == CH_ETEMON)



@etemon.on_talk
def challenge_etemon():
    if challenger != CH_ETEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("etemon.challenge.retry"))
        else:
            say(t("etemon.challenge.intro1"), t("etemon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(etemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("etemon.challenge.won"))
                give(Item.GoldBanana)
                give(bits=4000)
                narrator.say(t("etemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-750, -400)
                leave()
