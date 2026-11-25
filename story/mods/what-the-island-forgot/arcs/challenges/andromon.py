# Factorial Town 161: Andromon, near where it was recruited in the original game; it runs the remodel service.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_ANDROMON

site = screen(Screen.factorial_town_161)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Andromon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
andromon = site.npc(Species.Andromon, at=(-750, 1250), bits=300, range=0, still=True, when=challenger == CH_ANDROMON, alone=challenger == CH_ANDROMON)



@andromon.on_talk
def challenge_andromon():
    if challenger != CH_ANDROMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("andromon.challenge.retry"))
        else:
            say(t("andromon.challenge.intro1"), t("andromon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(andromon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("andromon.challenge.won"))
                give(Item.DefChip)
                give(bits=4000)
                narrator.say(t("andromon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(750, -750)
                leave()
