# Drill Tunnel 2nd floor 25: Ogremon, recruited here in the original game; it lives in the city (city/lower-city.py).
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_OGREMON

site = screen(Screen.drill_tunnel_2nd_floor_25)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Ogremon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home. (`recruited` is always true on its day: it
# tells the heap check that the screen's Ogremon-and-Agumon ambush, which needs it unrecruited, is not set up beside it.)
ogremon = site.npc(Species.Ogremon, at=(250, -600), hp=3600, mp=3500, offense=450, defense=260, speed=200, brain=150, bits=300, range=0, still=True, when=challenger == CH_OGREMON and recruited(Species.Ogremon), alone=challenger == CH_OGREMON)



@ogremon.on_talk
def challenge_ogremon():
    if challenger != CH_OGREMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("ogremon.challenge.retry"))
        else:
            say(t("ogremon.challenge.intro1"), t("ogremon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(ogremon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("ogremon.challenge.won"))
                give(Item.SpikeClub)
                give(bits=2500)
                narrator.say(t("ogremon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(2650, 100)
                leave()
