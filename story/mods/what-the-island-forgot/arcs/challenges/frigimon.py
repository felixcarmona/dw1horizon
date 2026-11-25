# Freezeland 137: Frigimon, recruited here in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_FRIGIMON

site = screen(Screen.freezeland_137)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Frigimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
frigimon = site.npc(Species.Frigimon, at=(-200, 300), bits=300, range=0, still=True, when=recruited(Species.Frigimon))


@site.on_enter(when=recruited(Species.Frigimon))
def challenge_away_frigimon():
    if not engine.game_beaten or challenger != CH_FRIGIMON or challenge_won:
        frigimon.leave()


@frigimon.on_talk
def challenge_frigimon():
    if challenger != CH_FRIGIMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("frigimon.challenge.retry"))
        else:
            say(t("frigimon.challenge.intro1"), t("frigimon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(frigimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("frigimon.challenge.won"))
                give(Item.IceCrystal)
                give(bits=2500)
                narrator.say(t("frigimon.challenge.reward"))
                challenge_won.set()
                run(-50, 1000)
                leave()
