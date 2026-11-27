# Freezeland 95: Garurumon, recruited here in the original game; it works at the Restaurant.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_GARURUMON

site = screen(Screen.freezeland_95)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Garurumon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
garurumon = site.npc(Species.Garurumon, at=(-200, -100), hp=4200, mp=4500, offense=580, defense=320, speed=240, brain=150, bits=300, range=0, still=True, when=challenger == CH_GARURUMON, alone=challenger == CH_GARURUMON)



@garurumon.on_talk
def challenge_garurumon():
    if challenger != CH_GARURUMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("garurumon.challenge.retry"))
        else:
            say(t("garurumon.challenge.intro1"), t("garurumon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(garurumon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("garurumon.challenge.won"))
                give(Item.MoonMirror)
                give(bits=2500)
                narrator.say(t("garurumon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(1300, 1900)
                leave()
