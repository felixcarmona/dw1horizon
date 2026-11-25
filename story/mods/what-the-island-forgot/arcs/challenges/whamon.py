# Secret Beach Cave 142: Whamon, recruited here in the original game; it runs the city dock ferry.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_WHAMON

site = screen(Screen.secret_beach_cave_142)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Whamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
whamon = site.npc(Species.Whamon, at=(-50, 1800), bits=300, range=0, still=True, when=challenger == CH_WHAMON, alone=challenger == CH_WHAMON)



@whamon.on_talk
def challenge_whamon():
    if challenger != CH_WHAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("whamon.challenge.retry"))
        else:
            say(t("whamon.challenge.intro1"), t("whamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(whamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("whamon.challenge.won"))
                give(Item.Digiseabass)
                give(bits=2500)
                narrator.say(t("whamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-150, 850)
                leave()
