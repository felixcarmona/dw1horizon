# Dragon Eye Lake 6: Coelamon, near where it was recruited in the original game; it lives in the city (city/centar-clinic.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_COELAMON

site = screen(Screen.dragon_eye_lake_6)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Coelamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
coelamon = site.npc(Species.Coelamon, at=(400, -1500), bits=300, range=0, still=True, when=recruited(Species.Coelamon))


@site.on_enter(when=recruited(Species.Coelamon))
def challenge_away_coelamon():
    if not engine.game_beaten or challenger != CH_COELAMON or challenge_won:
        coelamon.leave()


@coelamon.on_talk
def challenge_coelamon():
    if challenger != CH_COELAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("coelamon.challenge.retry"))
        else:
            say(t("coelamon.challenge.intro1"), t("coelamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(coelamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("coelamon.challenge.won"))
                give(Item.HardScale)
                give(bits=2500)
                narrator.say(t("coelamon.challenge.reward"))
                challenge_won.set()
                run(1100, -3900)
                leave()
