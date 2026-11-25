# Freezeland 133: Mojyamon, recruited here in the original game; it runs the trades.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_MOJYAMON

site = screen(Screen.freezeland_133)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mojyamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
mojyamon = site.npc(Species.Mojyamon, at=(2000, -3400), bits=300, range=0, still=True, when=recruited(Species.Mojyamon))


@site.on_enter(when=recruited(Species.Mojyamon))
def challenge_away_mojyamon():
    if not engine.game_beaten or challenger != CH_MOJYAMON or challenge_won:
        mojyamon.leave()


@mojyamon.on_talk
def challenge_mojyamon():
    if challenger != CH_MOJYAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("mojyamon.challenge.retry"))
        else:
            say(t("mojyamon.challenge.intro1"), t("mojyamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(mojyamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mojyamon.challenge.won"))
                give(Item.HairGrower)
                give(bits=2500)
                narrator.say(t("mojyamon.challenge.reward"))
                challenge_won.set()
                run(2000, -900)
                leave()
