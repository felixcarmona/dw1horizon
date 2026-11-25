# Lava Cave 125: Candlemon, its flame nearly out. A friendly fight, weaker than the zone's. Its home is the Forge
# (district/forge-workshop.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_CANDLEMON

cave = screen(Screen.lava_cave_125)
candlemon = cave.npc(Species.Candlemon, at=(2500, -650), hp=700, mp=1200, offense=200, defense=90, speed=80, brain=80, bits=200,
                     range=0, still=True, when=not recruited(Species.Candlemon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Candlemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
@cave.on_enter(when=recruited(Species.Candlemon) and engine.game_beaten)
def challenge_away():
    if challenger != CH_CANDLEMON or challenge_won:
        candlemon.leave()


def challenge():
    if challenger != CH_CANDLEMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("candlemon.challenge.retry"))
        else:
            say(t("candlemon.challenge.intro1"), t("candlemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(candlemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("candlemon.challenge.won"))
                give(Item.Fireball)
                give(bits=1500)
                narrator.say(t("candlemon.challenge.reward"))
                challenge_won.set()
                run(2950, 550)
                leave()


@candlemon.on_talk
def talk():
    if recruited(Species.Candlemon):
        challenge()
    else:
        say("Too hot to die, too small to burn.")
        say("Give me a good fight. It's the only thing that still lights me.")
        if fight(candlemon) == "won":
            say("That lit me up! Have you got a forge?")
            send_to_city(line="Candlemon joined the city!", species=Species.Candlemon)
