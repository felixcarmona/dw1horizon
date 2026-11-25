# Dragon Eye Lake 6: Seadramon, near where it was recruited in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_SEADRAMON

site = screen(Screen.dragon_eye_lake_6)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Seadramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
seadramon = site.npc(Species.Seadramon, at=(900, -750), bits=300, range=0, still=True, when=challenger == CH_SEADRAMON, alone=challenger == CH_SEADRAMON)



@seadramon.on_talk
def challenge_seadramon():
    if challenger != CH_SEADRAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("seadramon.challenge.retry"))
        else:
            say(t("seadramon.challenge.intro1"), t("seadramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(seadramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("seadramon.challenge.won"))
                give(Item.CoralCharm)
                give(bits=2500)
                narrator.say(t("seadramon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1600, -3150)
                leave()
