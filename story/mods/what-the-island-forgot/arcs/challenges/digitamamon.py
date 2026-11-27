# Mt. Infinity 219: Digitamamon, near where it was recruited in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_DIGITAMAMON

site = screen(Screen.mt_infinity_219)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Digitamamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
digitamamon = site.npc(Species.Digitamamon, at=(250, 1050), hp=9999, mp=9999, offense=999, defense=720, speed=500, brain=700, bits=300, range=0, still=True, when=challenger == CH_DIGITAMAMON, alone=challenger == CH_DIGITAMAMON)



@digitamamon.on_talk
def challenge_digitamamon():
    if challenger != CH_DIGITAMAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("digitamamon.challenge.retry"))
        else:
            say(t("digitamamon.challenge.intro1"), t("digitamamon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(digitamamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("digitamamon.challenge.won"))
                give(Item.MystyEgg)
                give(bits=4000)
                narrator.say(t("digitamamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-2150, 1750)
                leave()
