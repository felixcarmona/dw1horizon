# Ancient Speedy Region 86: Nanimon, recruited here in the original game; it lives in the city (city/item-keeper.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_NANIMON

site = screen(Screen.ancient_speedy_region_86)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Nanimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
nanimon = site.npc(Species.Nanimon, at=(-350, 1400), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_NANIMON, alone=challenger == CH_NANIMON)



@nanimon.on_talk
def challenge_nanimon():
    if challenger != CH_NANIMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("nanimon.challenge.retry"))
        else:
            say(t("nanimon.challenge.intro1"), t("nanimon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(nanimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("nanimon.challenge.won"))
                give(Item.Sunglasses)
                give(bits=2500)
                narrator.say(t("nanimon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(100, -1050)
                leave()
