# Mt. Infinity 222, the long hall before the top (the brief's 229 reads no NPC list): Knightmon guards a door to nothing.
# The hardest fight of the residents, above the mountain's wild Digimon. Its home is the Guard House (district/guard-house.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KNIGHTMON

hall = screen(Screen.mt_infinity_222)
knightmon = hall.npc(Species.Knightmon, at=(-900, 100), hp=4500, mp=5000, offense=720, defense=380, speed=300, brain=300, bits=2000,
                     range=0, still=True, when=not recruited(Species.Knightmon) or new_challenger == CH_KNIGHTMON, alone=new_challenger == CH_KNIGHTMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Knightmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/guard-house.py).

def challenge_knightmon():
    if new_challenger != CH_KNIGHTMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("knightmon.challenge.retry"))
        else:
            say(t("knightmon.challenge.intro1"), t("knightmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(knightmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("knightmon.challenge.won"))
                give(Item.Protection)
                give(bits=4000)
                narrator.say(t("knightmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(250, 2100)
                leave()


@knightmon.on_talk
def talk():
    if recruited(Species.Knightmon):
        challenge_knightmon()
    else:
        say("Halt. Nobody passes.")
        tamer.say("Passes what? There's nothing behind you.")
        if fight(knightmon, escape=False) == "won":
            say("My post is gone, but my oath is not. Name a wall and I will guard it.")
            run(-250, 150)
            send_to_city(line="Knightmon joined the city!", species=Species.Knightmon, camera=False)
