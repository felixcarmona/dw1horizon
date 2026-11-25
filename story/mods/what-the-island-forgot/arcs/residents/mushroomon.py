# Mt. Panorama's Spore Area 234: Mushroomon sneezes spores at whoever passes. A fight at the mountain's wild strength; its
# home is the Clinic (city/centar-clinic.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_MUSHROOMON

area = screen(Screen.mt_panorama_spore_area_234)
mushroomon = area.npc(Species.Mushroomon, at=(-450, -900), hp=1200, mp=2000, offense=300, defense=150, speed=120, brain=100, bits=300,
                      range=0, still=True, when=not recruited(Species.Mushroomon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mushroomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
@area.on_enter(when=recruited(Species.Mushroomon) and engine.game_beaten)
def challenge_away():
    if challenger != CH_MUSHROOMON or challenge_won:
        mushroomon.leave()


def challenge():
    if challenger != CH_MUSHROOMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("mushroomon.challenge.retry"))
        else:
            say(t("mushroomon.challenge.intro1"), t("mushroomon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(mushroomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mushroomon.challenge.won"))
                give(Item.Deluxmushrm)
                give(bits=1500)
                narrator.say(t("mushroomon.challenge.reward"))
                challenge_won.set()
                run(-250, -2050)
                leave()


@mushroomon.on_talk
def talk():
    if recruited(Species.Mushroomon):
        challenge()
    else:
        say("Ah... ah... AH-CHOO!")
        tamer.say("Cough, cough! What is all this dust?")
        say("Spores. Nobody stays on their feet for long around me.")
        if fight(mushroomon) == "won":
            say("You're not sick. Interesting. I could learn medicine from you.")
            send_to_city(line="Mushroomon joined the city!", species=Species.Mushroomon)
