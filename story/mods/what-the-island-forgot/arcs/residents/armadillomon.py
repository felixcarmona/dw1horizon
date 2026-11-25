# Ancient Speedy Region 85, the quiet end of the valley (the brief's 84 reads no NPC list): Armadillomon, half buried, is
# sure of its treasure and will not share the spot without a tussle. Its home is the Courtyard (district/the-courtyard.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_ARMADILLOMON

valley = screen(Screen.ancient_speedy_region_85)
armadillomon = valley.npc(Species.Armadillomon, at=(-600, 800), hp=1800, mp=2000, offense=300, defense=180, speed=150, brain=100, bits=600,
                          range=0, still=True, when=not recruited(Species.Armadillomon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Armadillomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
@valley.on_enter(when=recruited(Species.Armadillomon) and engine.game_beaten)
def challenge_away():
    if challenger != CH_ARMADILLOMON or challenge_won:
        armadillomon.leave()


def challenge():
    if challenger != CH_ARMADILLOMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("armadillomon.challenge.retry"))
        else:
            say(t("armadillomon.challenge.intro1"), t("armadillomon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(armadillomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("armadillomon.challenge.won"))
                give(Item.GoldAcorn)
                give(bits=1500)
                narrator.say(t("armadillomon.challenge.reward"))
                challenge_won.set()
                run(-150, -950)
                leave()


@armadillomon.on_talk
def talk():
    if recruited(Species.Armadillomon):
        challenge()
    else:
        say("Treasure! I swear there's treasure right under here!")
        say("This is my hole! Find your own!")
        # Scripted battles keep the defeated NPC for its reply instead of fleeing first.
        if fight(armadillomon, escape=False) == "won":
            say("Nothing down there but more dirt anyway.")
            say("Somebody in the city must be hiding better things.")
            run(-128, -1500)
            send_to_city(line="Armadillomon joined the city!", species=Species.Armadillomon)
