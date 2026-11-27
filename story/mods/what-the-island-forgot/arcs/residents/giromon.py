# Factorial Town 159: Giromon, recruited here in the original game, lives at the Restaurant (city/restaurant-215.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_GIROMON

town = screen(Screen.factorial_town_159)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Giromon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home, at the Restaurant (city/restaurant-215.py).
giromon = town.npc(Species.Giromon, at=(1250, 450), hp=5700, mp=4800, offense=690, defense=450, speed=490, brain=300, bits=300, range=0, still=True, when=challenger == CH_GIROMON, alone=challenger == CH_GIROMON)



@giromon.on_talk
def challenge_giromon():
    if challenger != CH_GIROMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("giromon.challenge.retry"))
        else:
            say(t("giromon.challenge.intro1"), t("giromon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(giromon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("giromon.challenge.won"))
                give(Item.SilverBall)
                give(bits=4000)
                narrator.say(t("giromon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(3650, -250)
                leave()
