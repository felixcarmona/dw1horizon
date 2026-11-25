# Gear Savanna 73: Biyomon, recruited here in the original game; it works at the item shop.
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_BIYOMON

site = screen(Screen.gear_savanna_73)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Biyomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
biyomon = site.npc(Species.Biyomon, at=(-1050, 2750), bits=300, range=0, still=True, when=recruited(Species.Biyomon))


@site.on_enter(when=recruited(Species.Biyomon))
def challenge_away_biyomon():
    if not engine.game_beaten or challenger != CH_BIYOMON or challenge_won:
        biyomon.leave()


@biyomon.on_talk
def challenge_biyomon():
    if challenger != CH_BIYOMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("biyomon.challenge.retry"))
        else:
            say(t("biyomon.challenge.intro1"), t("biyomon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(biyomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("biyomon.challenge.won"))
                give(Item.SweetNut)
                give(bits=1500)
                narrator.say(t("biyomon.challenge.reward"))
                challenge_won.set()
                run(-1750, 350)
                leave()
