# Native Forest 2: Palmon, recruited here in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_PALMON

site = screen(Screen.native_forest_2)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Palmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
palmon = site.npc(Species.Palmon, at=(1750, 2450), bits=300, range=0, still=True, when=recruited(Species.Palmon))


@site.on_enter(when=recruited(Species.Palmon))
def challenge_away_palmon():
    if not engine.game_beaten or challenger != CH_PALMON or challenge_won:
        palmon.leave()


@palmon.on_talk
def challenge_palmon():
    if challenger != CH_PALMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("palmon.challenge.retry"))
        else:
            say(t("palmon.challenge.intro1"), t("palmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(palmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("palmon.challenge.won"))
                give(Item.Digipine)
                give(bits=1500)
                narrator.say(t("palmon.challenge.reward"))
                challenge_won.set()
                run(250, 450)
                leave()
