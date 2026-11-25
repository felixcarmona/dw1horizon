# Mangrove Region 15: Betamon, recruited here in the original game; it keeps a shop in the lower city.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_BETAMON

site = screen(Screen.mangrove_region_15)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Betamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
betamon = site.npc(Species.Betamon, at=(350, 1700), bits=300, range=0, still=True, when=recruited(Species.Betamon))


@site.on_enter(when=recruited(Species.Betamon))
def challenge_away_betamon():
    if not engine.game_beaten or challenger != CH_BETAMON or challenge_won:
        betamon.leave()


@betamon.on_talk
def challenge_betamon():
    if challenger != CH_BETAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("betamon.challenge.retry"))
        else:
            say(t("betamon.challenge.intro1"), t("betamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(betamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("betamon.challenge.won"))
                give(Item.Waterbottle)
                give(bits=1500)
                narrator.say(t("betamon.challenge.reward"))
                challenge_won.set()
                run(-2150, 1700)
                leave()
