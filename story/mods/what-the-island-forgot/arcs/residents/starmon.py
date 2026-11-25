# Mt. Panorama's Spore Area 233: Starmon looks up at where it fell from, and fights for the fun of it, at the mountain's
# wild strength. Its home is the Container House (district/container-house.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_STARMON

ledge = screen(Screen.mt_panorama_spore_area_233)
starmon = ledge.npc(Species.Starmon, at=(1000, -1000), hp=1200, mp=2000, offense=300, defense=150, speed=130, brain=100, bits=300,
                    range=0, still=True, when=not recruited(Species.Starmon) or new_challenger == CH_STARMON, alone=new_challenger == CH_STARMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Starmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.

def challenge():
    if new_challenger != CH_STARMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("starmon.challenge.retry"))
        else:
            say(t("starmon.challenge.intro1"), t("starmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(starmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("starmon.challenge.won"))
                give(Item.NorthStar)
                give(bits=2500)
                narrator.say(t("starmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(1850, 150)
                leave()


@starmon.on_talk
def talk():
    if recruited(Species.Starmon):
        challenge()
    else:
        say("Do you know how far I've fallen?")
        say("Never mind. Want to see some stars?")
        if fight(starmon) == "won":
            say("A hit like that! The city must be full of stars.")
            send_to_city(line="Starmon joined the city!", species=Species.Starmon)
