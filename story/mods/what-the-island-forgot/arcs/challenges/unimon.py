# Mt. Panorama Spore Area 21: Unimon, near where it was recruited in the original game; it works at the item shop.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_UNIMON

site = screen(Screen.mt_panorama_spore_area_21)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Unimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
unimon = site.npc(Species.Unimon, at=(750, 1800), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_UNIMON, alone=challenger == CH_UNIMON)



@unimon.on_talk
def challenge_unimon():
    if challenger != CH_UNIMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("unimon.challenge.retry"))
        else:
            say(t("unimon.challenge.intro1"), t("unimon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(unimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("unimon.challenge.won"))
                give(Item.Unihorn)
                give(bits=2500)
                narrator.say(t("unimon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-1250, 300)
                leave()
