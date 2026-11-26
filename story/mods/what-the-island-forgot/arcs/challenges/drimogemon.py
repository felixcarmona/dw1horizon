# Drill Tunnel 32: Drimogemon, recruited here in the original game; it runs the treasure hunt.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_DRIMOGEMON

site = screen(Screen.drill_tunnel_32)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Drimogemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
drimogemon = site.npc(Species.Drimogemon, at=(-400, -1400), hp=3750, mp=3500, offense=470, defense=240, speed=290, brain=200, bits=300, range=0, still=True, when=challenger == CH_DRIMOGEMON, alone=challenger == CH_DRIMOGEMON)



@drimogemon.on_talk
def challenge_drimogemon():
    if challenger != CH_DRIMOGEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("drimogemon.challenge.retry"))
        else:
            say(t("drimogemon.challenge.intro1"), t("drimogemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(drimogemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("drimogemon.challenge.won"))
                give(Item.Digimushrm)
                give(bits=2500)
                narrator.say(t("drimogemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(300, 1000)
                leave()
