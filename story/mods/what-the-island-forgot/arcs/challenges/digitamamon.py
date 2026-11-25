# Mt. Infinity 219: Digitamamon, near where it was recruited in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_DIGITAMAMON

site = screen(Screen.mt_infinity_219)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Digitamamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
digitamamon = site.npc(Species.Digitamamon, at=(250, 1050), bits=300, range=0, still=True, when=recruited(Species.Digitamamon))


@site.on_enter(when=recruited(Species.Digitamamon))
def challenge_away_digitamamon():
    if not engine.game_beaten or challenger != CH_DIGITAMAMON or challenge_won:
        digitamamon.leave()


@digitamamon.on_talk
def challenge_digitamamon():
    if challenger != CH_DIGITAMAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("digitamamon.challenge.retry"))
        else:
            say(t("digitamamon.challenge.intro1"), t("digitamamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(digitamamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("digitamamon.challenge.won"))
                give(Item.MystyEgg)
                give(bits=4000)
                narrator.say(t("digitamamon.challenge.reward"))
                challenge_won.set()
                run(-2150, 1750)
                leave()
