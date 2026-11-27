# Great Canyon 127: Shellmon, recruited here in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_SHELLMON

site = screen(Screen.great_canyon_127)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Shellmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
shellmon = site.npc(Species.Shellmon, at=(2150, -1400), hp=2500, mp=2500, offense=250, defense=250, speed=250, brain=250, bits=300, range=0, still=True, when=challenger == CH_SHELLMON, alone=challenger == CH_SHELLMON)



@shellmon.on_talk
def challenge_shellmon():
    if challenger != CH_SHELLMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("shellmon.challenge.retry"))
        else:
            say(t("shellmon.challenge.intro1"), t("shellmon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(shellmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("shellmon.challenge.won"))
                give(Item.RedShell)
                give(bits=2500)
                narrator.say(t("shellmon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(650, -2100)
                leave()
