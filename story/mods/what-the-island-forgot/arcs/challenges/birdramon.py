# Great Canyon 128: Birdramon, near where it was recruited in the original game; it runs the transport.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_BIRDRAMON

site = screen(Screen.great_canyon_128)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Birdramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
birdramon = site.npc(Species.Birdramon, at=(1600, -1050), hp=3700, mp=3500, offense=490, defense=200, speed=340, brain=200, bits=300, range=0, still=True, when=challenger == CH_BIRDRAMON, alone=challenger == CH_BIRDRAMON)



@birdramon.on_talk
def challenge_birdramon():
    if challenger != CH_BIRDRAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("birdramon.challenge.retry"))
        else:
            say(t("birdramon.challenge.intro1"), t("birdramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(birdramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("birdramon.challenge.won"))
                give(Item.Flamingwing)
                give(bits=2500)
                narrator.say(t("birdramon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1600, 1450)
                leave()
