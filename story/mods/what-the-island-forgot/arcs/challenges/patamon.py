# Gear Savanna 72: Patamon, recruited here in the original game; it keeps the item shop.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_PATAMON

site = screen(Screen.gear_savanna_72)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Patamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
patamon = site.npc(Species.Patamon, at=(50, 400), hp=590, mp=610, offense=120, defense=90, speed=100, brain=80, bits=300, range=0, still=True, when=challenger == CH_PATAMON, alone=challenger == CH_PATAMON)



@patamon.on_talk
def challenge_patamon():
    if challenger != CH_PATAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("patamon.challenge.retry"))
        else:
            say(t("patamon.challenge.intro1"), t("patamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(patamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("patamon.challenge.won"))
                give(Item.SpeedLeaf)
                give(bits=1500)
                narrator.say(t("patamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(2050, -1100)
                leave()
