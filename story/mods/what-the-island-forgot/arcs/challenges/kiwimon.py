# Gear Savanna 77: Kiwimon was recruited on Gear Savanna 78 (arcs/residents/kiwimon.py, where Leomon waits), so it waits on 77; it lives in the city (city/restaurant-214.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_KIWIMON

site = screen(Screen.gear_savanna_77)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kiwimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kiwimon = site.npc(Species.Kiwimon, at=(400, -750), bits=300, range=0, still=True, when=recruited(Species.Kiwimon))


@site.on_enter(when=recruited(Species.Kiwimon))
def challenge_away_kiwimon():
    if not engine.game_beaten or challenger != CH_KIWIMON or challenge_won:
        kiwimon.leave()


@kiwimon.on_talk
def challenge_kiwimon():
    if challenger != CH_KIWIMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kiwimon.challenge.retry"))
        else:
            say(t("kiwimon.challenge.intro1"), t("kiwimon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kiwimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kiwimon.challenge.won"))
                give(Item.BlueApple)
                give(bits=2500)
                narrator.say(t("kiwimon.challenge.reward"))
                challenge_won.set()
                run(1900, 1250)
                leave()
