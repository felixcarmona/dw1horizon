# Beetle Land 107: Kabuterimon, recruited here in the original game; it lives in the city (city/green-gym.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KABUTERIMON

site = screen(Screen.beetle_land_107)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kabuterimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kabuterimon = site.npc(Species.Kabuterimon, at=(-1650, -450), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_KABUTERIMON, alone=challenger == CH_KABUTERIMON)



@kabuterimon.on_talk
def challenge_kabuterimon():
    if challenger != CH_KABUTERIMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kabuterimon.challenge.retry"))
        else:
            say(t("kabuterimon.challenge.intro1"), t("kabuterimon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kabuterimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kabuterimon.challenge.won"))
                give(Item.Beetlepearl)
                give(bits=2500)
                narrator.say(t("kabuterimon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(850, -450)
                leave()
