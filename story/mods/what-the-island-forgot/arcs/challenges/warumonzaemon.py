# Toy Mansion 149: WaruMonzaemon, near where it was recruited in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_WARUMONZAEMON

site = screen(Screen.toy_mansion_149)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day WaruMonzaemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
warumonzaemon = site.npc(Species.WaruMonzaemon, at=(0, -250), bits=300, range=0, still=True, when=recruited(Species.WaruMonzaemon))


@site.on_enter(when=recruited(Species.WaruMonzaemon))
def challenge_away_warumonzaemon():
    if not engine.game_beaten or challenger != CH_WARUMONZAEMON or challenge_won:
        warumonzaemon.leave()


@warumonzaemon.on_talk
def challenge_warumonzaemon():
    if challenger != CH_WARUMONZAEMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("warumonzaemon.challenge.retry"))
        else:
            say(t("warumonzaemon.challenge.intro1"), t("warumonzaemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(warumonzaemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("warumonzaemon.challenge.won"))
                give(Item.XBandage)
                give(bits=4000)
                narrator.say(t("warumonzaemon.challenge.reward"))
                challenge_won.set()
                run(1450, 800)
                leave()
