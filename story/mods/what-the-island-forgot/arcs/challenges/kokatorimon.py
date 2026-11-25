# Misty Trees 117: Kokatorimon, recruited here in the original game; it lives in the city (city/file-city-services.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_KOKATORIMON

site = screen(Screen.misty_trees_117)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kokatorimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kokatorimon = site.npc(Species.Kokatorimon, at=(-500, 1200), bits=300, range=0, still=True, when=recruited(Species.Kokatorimon))


@site.on_enter(when=recruited(Species.Kokatorimon))
def challenge_away_kokatorimon():
    if not engine.game_beaten or challenger != CH_KOKATORIMON or challenge_won:
        kokatorimon.leave()


@kokatorimon.on_talk
def challenge_kokatorimon():
    if challenger != CH_KOKATORIMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("kokatorimon.challenge.retry"))
        else:
            say(t("kokatorimon.challenge.intro1"), t("kokatorimon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(kokatorimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kokatorimon.challenge.won"))
                give(Item.Rooster)
                give(bits=2500)
                narrator.say(t("kokatorimon.challenge.reward"))
                challenge_won.set()
                run(-1200, -1200)
                leave()
