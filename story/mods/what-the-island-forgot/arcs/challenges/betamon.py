# Mangrove Region 15: Betamon, recruited here in the original game; it keeps a shop in the lower city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_BETAMON

site = screen(Screen.mangrove_region_15)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Betamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
betamon = site.npc(Species.Betamon, at=(350, 1700), bits=300, range=0, still=True, when=challenger == CH_BETAMON, alone=challenger == CH_BETAMON)



@betamon.on_talk
def challenge_betamon():
    if challenger != CH_BETAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("betamon.challenge.retry"))
        else:
            say(t("betamon.challenge.intro1"), t("betamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(betamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("betamon.challenge.won"))
                give(Item.Waterbottle)
                give(bits=1500)
                narrator.say(t("betamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-2150, 1700)
                leave()
