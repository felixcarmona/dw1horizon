# The Toy Mansion's hall 147, at night only (Toy Town 144 has no heap for a fourth model): Pumpkinmon wants a game. A fight at
# Toy Town's strength. Its home is the Scrap Office (district/scrap-office.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_PUMPKINMON

hall = screen(Screen.toy_mansion_147)
pumpkinmon = hall.npc(Species.Pumpkinmon, at=(-1300, 700), hp=1400, mp=2000, offense=260, defense=130, speed=120, brain=100, bits=300,
                      range=0, still=True, when=clock.hour >= 20 or recruited(Species.Pumpkinmon))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Pumpkinmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/scrap-office.py).
@hall.on_enter(when=recruited(Species.Pumpkinmon))
def challenge_away_pumpkinmon():
    if not engine.game_beaten or challenger != CH_PUMPKINMON or challenge_won:
        pumpkinmon.leave()


def challenge_pumpkinmon():
    if challenger != CH_PUMPKINMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("pumpkinmon.challenge.retry"))
        else:
            say(t("pumpkinmon.challenge.intro1"), t("pumpkinmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(pumpkinmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("pumpkinmon.challenge.won"))
                give(Item.SuperVeggy)
                give(bits=4000)
                narrator.say(t("pumpkinmon.challenge.reward"))
                challenge_won.set()
                run(1200, 700)
                leave()


@pumpkinmon.on_talk
def talk():
    if recruited(Species.Pumpkinmon):
        challenge_pumpkinmon()
    else:
        say("Trick or treat! No? Then a game.")
        if fight(pumpkinmon) == "won":
            say("You don't scare easily. Good. I need customers like that.")
            send_to_city(line="Pumpkinmon joined the city!", species=Species.Pumpkinmon)
