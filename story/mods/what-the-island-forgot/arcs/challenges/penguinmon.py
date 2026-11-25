# Freezeland 134: Penguinmon, recruited here in the original game; it keeps the curling rink.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_PENGUINMON

site = screen(Screen.freezeland_134)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Penguinmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
penguinmon = site.npc(Species.Penguinmon, at=(1750, 1200), bits=300, range=0, still=True, when=recruited(Species.Penguinmon))


@site.on_enter(when=recruited(Species.Penguinmon))
def challenge_away_penguinmon():
    if not engine.game_beaten or challenger != CH_PENGUINMON or challenge_won:
        penguinmon.leave()


@penguinmon.on_talk
def challenge_penguinmon():
    if challenger != CH_PENGUINMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("penguinmon.challenge.retry"))
        else:
            say(t("penguinmon.challenge.intro1"), t("penguinmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(penguinmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("penguinmon.challenge.won"))
                give(Item.BlackTrout)
                give(bits=1500)
                narrator.say(t("penguinmon.challenge.reward"))
                challenge_won.set()
                run(-700, 950)
                leave()
