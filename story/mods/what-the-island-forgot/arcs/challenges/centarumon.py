# Amida Forest 17: Centarumon, recruited here in the original game; it keeps the clinic.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_CENTARUMON

site = screen(Screen.amida_forest)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Centarumon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
centarumon = site.npc(Species.Centarumon, at=(-1600, 4900), bits=300, range=0, still=True, when=recruited(Species.Centarumon))


@site.on_enter(when=recruited(Species.Centarumon))
def challenge_away_centarumon():
    if not engine.game_beaten or challenger != CH_CENTARUMON or challenge_won:
        centarumon.leave()


@centarumon.on_talk
def challenge_centarumon():
    if challenger != CH_CENTARUMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("centarumon.challenge.retry"))
        else:
            say(t("centarumon.challenge.intro1"), t("centarumon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(centarumon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("centarumon.challenge.won"))
                give(Item.IronHoof)
                give(bits=2500)
                narrator.say(t("centarumon.challenge.reward"))
                challenge_won.set()
                run(-1600, 2400)
                leave()
