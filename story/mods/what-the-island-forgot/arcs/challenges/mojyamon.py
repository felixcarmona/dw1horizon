# Freezeland 133: Mojyamon, recruited here in the original game; it runs the trades.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MOJYAMON

site = screen(Screen.freezeland_133)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mojyamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
mojyamon = site.npc(Species.Mojyamon, at=(2000, -3400), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_MOJYAMON, alone=challenger == CH_MOJYAMON)



@mojyamon.on_talk
def challenge_mojyamon():
    if challenger != CH_MOJYAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("mojyamon.challenge.retry"))
        else:
            say(t("mojyamon.challenge.intro1"), t("mojyamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(mojyamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mojyamon.challenge.won"))
                give(Item.HairGrower)
                give(bits=2500)
                narrator.say(t("mojyamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(2000, -900)
                leave()
