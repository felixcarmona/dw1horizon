# Mt. Panorama Plains 19: Mamemon, recruited here in the original game; it works at the secret item shop.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MAMEMON

site = screen(Screen.mt_panorama_plains)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Mamemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
mamemon = site.npc(Species.Mamemon, at=(2850, 1450), hp=4800, mp=4600, offense=650, defense=480, speed=520, brain=550, bits=300, range=0, still=True, when=challenger == CH_MAMEMON, alone=challenger == CH_MAMEMON)



@mamemon.on_talk
def challenge_mamemon():
    if challenger != CH_MAMEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("mamemon.challenge.retry"))
        else:
            say(t("mamemon.challenge.intro1"), t("mamemon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(mamemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("mamemon.challenge.won"))
                give(Item.OffChip)
                give(bits=4000)
                narrator.say(t("mamemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(850, -50)
                leave()
