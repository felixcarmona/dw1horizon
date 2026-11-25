# Path Thru Mt. Panorama 20: Vademon, near where it was recruited in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_VADEMON

site = screen(Screen.path_thru_mt_panorama_20)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Vademon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
vademon = site.npc(Species.Vademon, at=(0, -800), bits=300, range=0, still=True, when=recruited(Species.Vademon))


@site.on_enter(when=recruited(Species.Vademon))
def challenge_away_vademon():
    if not engine.game_beaten or challenger != CH_VADEMON or challenge_won:
        vademon.leave()


@vademon.on_talk
def challenge_vademon():
    if challenger != CH_VADEMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("vademon.challenge.retry"))
        else:
            say(t("vademon.challenge.intro1"), t("vademon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(vademon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("vademon.challenge.won"))
                give(Item.RayGun)
                give(bits=4000)
                narrator.say(t("vademon.challenge.reward"))
                challenge_won.set()
                run(0, -3300)
                leave()
