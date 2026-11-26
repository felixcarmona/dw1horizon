# Misty Trees 119: Kokatorimon, near where it was recruited in the original game; it lives in the city (city/file-city-services.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KOKATORIMON

site = screen(Screen.misty_trees_119)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kokatorimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kokatorimon = site.npc(Species.Kokatorimon, at=(0, -1800), hp=4200, mp=4800, offense=600, defense=240, speed=360, brain=100, bits=300, range=0, still=True, when=challenger == CH_KOKATORIMON, alone=challenger == CH_KOKATORIMON)



@kokatorimon.on_talk
def challenge_kokatorimon():
    if challenger != CH_KOKATORIMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kokatorimon.challenge.retry"))
        else:
            say(t("kokatorimon.challenge.intro1"), t("kokatorimon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kokatorimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kokatorimon.challenge.won"))
                give(Item.Rooster)
                give(bits=2500)
                narrator.say(t("kokatorimon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(0, -3500)
                leave()
