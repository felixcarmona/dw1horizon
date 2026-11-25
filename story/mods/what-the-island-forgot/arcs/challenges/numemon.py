# Sewer 220: Numemon, recruited here in the original game; it keeps the secret item shop.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_NUMEMON

site = screen(Screen.sewer_220)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Numemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
numemon = site.npc(Species.Numemon, at=(3350, -750), bits=300, range=0, still=True, when=recruited(Species.Numemon))


@site.on_enter(when=recruited(Species.Numemon))
def challenge_away_numemon():
    if not engine.game_beaten or challenger != CH_NUMEMON or challenge_won:
        numemon.leave()


@numemon.on_talk
def challenge_numemon():
    if challenger != CH_NUMEMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("numemon.challenge.retry"))
        else:
            say(t("numemon.challenge.intro1"), t("numemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(numemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("numemon.challenge.won"))
                give(Item.Happymushrm)
                give(bits=2500)
                narrator.say(t("numemon.challenge.reward"))
                challenge_won.set()
                run(1100, -1700)
                leave()
