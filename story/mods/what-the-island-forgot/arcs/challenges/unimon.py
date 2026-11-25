# Mt. Panorama Spore Area 21: Unimon, near where it was recruited in the original game; it works at the item shop.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_UNIMON

site = screen(Screen.mt_panorama_spore_area_21)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Unimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
unimon = site.npc(Species.Unimon, at=(750, 1800), bits=300, range=0, still=True, when=recruited(Species.Unimon))


@site.on_enter(when=recruited(Species.Unimon))
def challenge_away_unimon():
    if not engine.game_beaten or challenger != CH_UNIMON or challenge_won:
        unimon.leave()


@unimon.on_talk
def challenge_unimon():
    if challenger != CH_UNIMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("unimon.challenge.retry"))
        else:
            say(t("unimon.challenge.intro1"), t("unimon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(unimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("unimon.challenge.won"))
                give(Item.Unihorn)
                give(bits=2500)
                narrator.say(t("unimon.challenge.reward"))
                challenge_won.set()
                run(-1250, 300)
                leave()
