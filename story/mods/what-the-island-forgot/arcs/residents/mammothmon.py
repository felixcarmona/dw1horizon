# Freezeland 94 (the brief's 92 reads no NPC list): Mammothmon has stood here since before the ice. An end-game fight, the
# strength of Mt. Infinity's wild Digimon. Its home is the Cold Store (district/cold-store.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MAMMOTHMON

field = screen(Screen.freezeland_94)
mammothmon = field.npc(Species.Mammothmon, at=(0, 450), hp=4650, mp=4000, offense=640, defense=340, speed=250, brain=200, bits=1500,
                       range=0, still=True, when=not recruited(Species.Mammothmon) or new_challenger == CH_MAMMOTHMON, alone=new_challenger == CH_MAMMOTHMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mammothmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/cold-store.py).

def challenge_mammothmon():
    if new_challenger != CH_MAMMOTHMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("mammothmon.challenge.retry"))
        else:
            say(t("mammothmon.challenge.intro1"), t("mammothmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(mammothmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mammothmon.challenge.won"))
                give(Item.PowerIce)
                give(bits=4000)
                narrator.say(t("mammothmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(1500, 2450)
                leave()


@mammothmon.on_talk
def talk():
    if recruited(Species.Mammothmon):
        challenge_mammothmon()
    else:
        say("I have stood here since before the ice.")
        if fight(mammothmon, escape=False) == "won":
            say("Warm hands. I had forgotten.")
            run(-1350, 350)
            send_to_city(line="Mammothmon joined the city!", species=Species.Mammothmon, camera=False)
