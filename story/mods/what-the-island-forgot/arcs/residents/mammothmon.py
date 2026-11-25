# Freezeland 94 (the brief's 92 reads no NPC list): Mammothmon has stood here since before the ice. An end-game fight, the
# strength of Mt. Infinity's wild Digimon. Its home is the Cold Store (district/cold-store.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_MAMMOTHMON

field = screen(Screen.freezeland_94)
mammothmon = field.npc(Species.Mammothmon, at=(0, 450), hp=4650, mp=4000, offense=640, defense=340, speed=250, brain=200, bits=1500,
                       range=0, still=True, when=not recruited(Species.Mammothmon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mammothmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
@field.on_enter(when=recruited(Species.Mammothmon) and engine.game_beaten)
def challenge_away():
    if challenger != CH_MAMMOTHMON or challenge_won:
        mammothmon.leave()


def challenge():
    if challenger != CH_MAMMOTHMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("mammothmon.challenge.retry"))
        else:
            say(t("mammothmon.challenge.intro1"), t("mammothmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(mammothmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mammothmon.challenge.won"))
                give(Item.IceCrystal)
                give(bits=4000)
                narrator.say(t("mammothmon.challenge.reward"))
                challenge_won.set()
                run(150, -850)
                leave()


@mammothmon.on_talk
def talk():
    if recruited(Species.Mammothmon):
        challenge()
    else:
        say("I have stood here since before the ice.")
        if fight(mammothmon) == "won":
            say("Warm hands. I had forgotten.")
            send_to_city(line="Mammothmon joined the city!", species=Species.Mammothmon)
