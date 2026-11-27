# Mt. Panorama's Spore Area 234: Mushroomon sneezes spores at whoever passes. A fight at the mountain's wild strength; its
# home is the Clinic (city/centar-clinic.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MUSHROOMON

area = screen(Screen.mt_panorama_spore_area_234)
mushroomon = area.npc(Species.Mushroomon, at=(-450, -900), hp=1200, mp=2000, offense=300, defense=150, speed=120, brain=100, bits=300,
                      range=0, still=True, when=not recruited(Species.Mushroomon) or new_challenger == CH_MUSHROOMON, alone=new_challenger == CH_MUSHROOMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mushroomon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (city/centar-clinic.py).

def challenge_mushroomon():
    if new_challenger != CH_MUSHROOMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("mushroomon.challenge.retry"))
        else:
            say(t("mushroomon.challenge.intro1"), t("mushroomon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(mushroomon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mushroomon.challenge.won"))
                give(Item.Deluxmushrm)
                give(bits=1500)
                narrator.say(t("mushroomon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(-450, 1600)
                leave()


@mushroomon.on_talk
def talk():
    if recruited(Species.Mushroomon):
        challenge_mushroomon()
    else:
        say("Ah... ah... AH-CHOO!")
        tamer.say("Cough, cough! What is all this dust?")
        say("Spores. Nobody stays on their feet for long around me.")
        if fight(mushroomon, escape=False) == "won":
            say("You're not sick. Interesting. I could learn medicine from you.")
            run(750, -850)
            send_to_city(line="Mushroomon joined the city!", species=Species.Mushroomon, camera=False)
