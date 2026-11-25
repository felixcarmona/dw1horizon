# Beetle Land 108: Kuwagamon, recruited here in the original game; it lives in the city (city/green-gym.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KUWAGAMON

site = screen(Screen.beetle_land_108)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kuwagamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kuwagamon = site.npc(Species.Kuwagamon, at=(50, 1800), bits=300, range=0, still=True, when=challenger == CH_KUWAGAMON, alone=challenger == CH_KUWAGAMON)



@kuwagamon.on_talk
def challenge_kuwagamon():
    if challenger != CH_KUWAGAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kuwagamon.challenge.retry"))
        else:
            say(t("kuwagamon.challenge.intro1"), t("kuwagamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kuwagamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kuwagamon.challenge.won"))
                give(Item.ScissorJaw)
                give(bits=2500)
                narrator.say(t("kuwagamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-1450, -200)
                leave()
