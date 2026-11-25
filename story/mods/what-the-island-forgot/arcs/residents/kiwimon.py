# Gear Savanna 78: Kiwimon will not move until somebody feeds it. A Meat, consumed. No fight. It cooks at the Restaurant
# (city/restaurant-214.py, city/restaurant-215.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_LEOMON

savanna = screen(Screen.gear_savanna_78)
kiwimon = savanna.npc(Species.Kiwimon, at=(-750, 1750), range=0, still=True, when=not recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("I'm not moving. I'm too hungry to move. Is that meat I smell?")
    if has(Item.Meat):
        if ask(yes="Give it a {item Item.Meat}", no=t("kiwimon.refuse")):
            take(Item.Meat)
            say("Finally, someone who understands food.")
            send_to_city(line="Kiwimon joined the city!", species=Species.Kiwimon)
    else:
        say("No? Then come back with a {item Item.Meat}. I'll be here. I told you, I'm not moving.")


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Leomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home, at Birdra Transport (city/birdra-transport.py).
leomon = savanna.npc(Species.Leomon, at=(-50, 3150), bits=300, range=0, still=True, when=recruited(Species.Leomon) and trigger(50))


@savanna.on_enter(when=recruited(Species.Leomon) and engine.game_beaten)
def challenge_away_leomon():
    if challenger != CH_LEOMON or challenge_won:
        leomon.leave()


@leomon.on_talk
def challenge_leomon():
    if challenger != CH_LEOMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("leomon.challenge.retry"))
        else:
            say(t("leomon.challenge.intro1"), t("leomon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(leomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("leomon.challenge.won"))
                give(Item.Flamingmane)
                give(bits=2500)
                narrator.say(t("leomon.challenge.reward"))
                challenge_won.set()
                run(-1650, 1250)
                leave()
