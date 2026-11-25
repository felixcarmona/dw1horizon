# Ancient Speedy Region 87, next door to the Ancient Dino Region (79 has no heap for its model): Triceramon pushes a rock. A hard
# fight, the strength of the Dino Region's Tyrannomon. Its home is the Forge (district/forge-workshop.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_TRICERAMON

region = screen(Screen.ancient_speedy_region_87)
triceramon = region.npc(Species.Triceramon, at=(400, -1200), hp=3100, mp=2800, offense=420, defense=240, speed=200, brain=200, bits=1200,
                        range=0, still=True, when=not recruited(Species.Triceramon) or new_challenger == CH_TRICERAMON, alone=new_challenger == CH_TRICERAMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Triceramon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.

def challenge():
    if new_challenger != CH_TRICERAMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("triceramon.challenge.retry"))
        else:
            say(t("triceramon.challenge.intro1"), t("triceramon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(triceramon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("triceramon.challenge.won"))
                give(Item.HornHelmet)
                give(bits=4000)
                narrator.say(t("triceramon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(1050, -1150)
                leave()


@triceramon.on_talk
def talk():
    if recruited(Species.Triceramon):
        challenge()
    else:
        say("It goes there.")
        tamer.say("Why there?")
        say("It goes there.")
        if fight(triceramon, escape=False) == "won":
            say("You have good shoulders. There is more rock in the city?")
            run(-950, -1450)
            send_to_city(line="Triceramon joined the city!", species=Species.Triceramon, camera=False)
