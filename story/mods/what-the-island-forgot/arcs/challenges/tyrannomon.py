# Ancient Glacial Region 82: Tyrannomon, recruited here in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_TYRANNOMON

site = screen(Screen.ancient_glacial_region_82)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Tyrannomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
tyrannomon = site.npc(Species.Tyrannomon, at=(-350, 2150), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_TYRANNOMON, alone=challenger == CH_TYRANNOMON)



@tyrannomon.on_talk
def challenge_tyrannomon():
    if challenger != CH_TYRANNOMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("tyrannomon.challenge.retry"))
        else:
            say(t("tyrannomon.challenge.intro1"), t("tyrannomon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(tyrannomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("tyrannomon.challenge.won"))
                give(Item.Sirloin)
                give(bits=2500)
                narrator.say(t("tyrannomon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-350, -350)
                leave()
