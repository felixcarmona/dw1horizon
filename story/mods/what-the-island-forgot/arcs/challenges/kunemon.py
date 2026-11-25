# Kunemon's Bed 1: Kunemon, recruited here in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_KUNEMON

site = screen(Screen.kunemons_bed)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kunemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kunemon = site.npc(Species.Kunemon, at=(-50, -800), bits=300, range=0, still=True, when=recruited(Species.Kunemon))


@site.on_enter(when=recruited(Species.Kunemon))
def challenge_away_kunemon():
    if not engine.game_beaten or challenger != CH_KUNEMON or challenge_won:
        kunemon.leave()


@kunemon.on_talk
def challenge_kunemon():
    if challenger != CH_KUNEMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kunemon.challenge.retry"))
        else:
            say(t("kunemon.challenge.intro1"), t("kunemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kunemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kunemon.challenge.won"))
                give(Item.CalmBerry)
                give(bits=1500)
                narrator.say(t("kunemon.challenge.reward"))
                challenge_won.set()
                run(1450, 1200)
                leave()
