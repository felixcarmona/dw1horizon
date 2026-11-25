# Underground Lab 68: SkullGreymon, near where it was recruited in the original game; it lives in the city.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_SKULLGREYMON

site = screen(Screen.underground_lab_68)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day SkullGreymon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
skullgreymon = site.npc(Species.SkullGreymon, at=(-450, 1500), bits=300, range=0, still=True, when=recruited(Species.SkullGreymon))


@site.on_enter(when=recruited(Species.SkullGreymon))
def challenge_away_skullgreymon():
    if not engine.game_beaten or challenger != CH_SKULLGREYMON or challenge_won:
        skullgreymon.leave()


@skullgreymon.on_talk
def challenge_skullgreymon():
    if challenger != CH_SKULLGREYMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("skullgreymon.challenge.retry"))
        else:
            say(t("skullgreymon.challenge.intro1"), t("skullgreymon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(skullgreymon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("skullgreymon.challenge.won"))
                give(Item.FatalBone)
                give(bits=4000)
                narrator.say(t("skullgreymon.challenge.reward"))
                challenge_won.set()
                run(2050, 1500)
                leave()
