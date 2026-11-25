# Freezeland 93: Angemon, near where it was recruited in the original game; it lives in the city (city/jijimons-house-205.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_ANGEMON

site = screen(Screen.freezeland_93)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Angemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
angemon = site.npc(Species.Angemon, at=(350, -650), bits=300, range=0, still=True, when=challenger == CH_ANGEMON, alone=challenger == CH_ANGEMON)



@angemon.on_talk
def challenge_angemon():
    if challenger != CH_ANGEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("angemon.challenge.retry"))
        else:
            say(t("angemon.challenge.intro1"), t("angemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(angemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("angemon.challenge.won"))
                give(Item.WhiteWing)
                give(bits=2500)
                narrator.say(t("angemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1850, 1350)
                leave()
