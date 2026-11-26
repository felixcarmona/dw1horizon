# Native Forest 111: Greymon, near where it was recruited in the original game; it keeps the arena desk.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_GREYMON

site = screen(Screen.native_forest_111)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Greymon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
greymon = site.npc(Species.Greymon, at=(-150, 750), hp=4800, mp=3800, offense=630, defense=340, speed=360, brain=200, bits=300, range=0, still=True, when=challenger == CH_GREYMON, alone=challenger == CH_GREYMON)



@greymon.on_talk
def challenge_greymon():
    if challenger != CH_GREYMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("greymon.challenge.retry"))
        else:
            say(t("greymon.challenge.intro1"), t("greymon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(greymon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("greymon.challenge.won"))
                give(Item.MetalPart)
                give(bits=2500)
                narrator.say(t("greymon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-1650, -1250)
                leave()
