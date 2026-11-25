# Lava Cave 31: Meramon, recruited here in the original game; it cooks at the Restaurant.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_MERAMON

site = screen(Screen.lava_cave_31)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Meramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
meramon = site.npc(Species.Meramon, at=(-1550, -200), bits=300, range=0, still=True, when=recruited(Species.Meramon))


@site.on_enter(when=recruited(Species.Meramon))
def challenge_away_meramon():
    if not engine.game_beaten or challenger != CH_MERAMON or challenge_won:
        meramon.leave()


@meramon.on_talk
def challenge_meramon():
    if challenger != CH_MERAMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("meramon.challenge.retry"))
        else:
            say(t("meramon.challenge.intro1"), t("meramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(meramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("meramon.challenge.won"))
                give(Item.GiantMeat)
                give(bits=2500)
                narrator.say(t("meramon.challenge.reward"))
                challenge_won.set()
                run(450, -1700)
                leave()
