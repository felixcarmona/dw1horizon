# Great Canyon Top Area 44: Monochromon, near where it was recruited in the original game; it works at the item shop.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MONOCHROMON

site = screen(Screen.great_canyon_top_area_44)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Monochromon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
monochromon = site.npc(Species.Monochromon, at=(-1350, -650), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_MONOCHROMON, alone=challenger == CH_MONOCHROMON)



@monochromon.on_talk
def challenge_monochromon():
    if challenger != CH_MONOCHROMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("monochromon.challenge.retry"))
        else:
            say(t("monochromon.challenge.intro1"), t("monochromon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(monochromon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("monochromon.challenge.won"))
                give(Item.MonoStone)
                give(bits=2500)
                narrator.say(t("monochromon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-400, -2650)
                leave()
