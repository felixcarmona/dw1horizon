# Gear Savanna 77: Kiwimon was recruited on Gear Savanna 78 (arcs/residents/kiwimon.py, where Leomon waits), so it waits on 77; it lives in the city (city/restaurant-214.py).
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_KIWIMON

site = screen(Screen.gear_savanna_77)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Kiwimon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
kiwimon = site.npc(Species.Kiwimon, at=(400, -750), hp=1490, mp=1460, offense=250, defense=195, speed=205, brain=185, bits=300, range=0, still=True, when=new_challenger == CH_KIWIMON, alone=new_challenger == CH_KIWIMON)



@kiwimon.on_talk
def challenge_kiwimon():
    if new_challenger != CH_KIWIMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("kiwimon.challenge.retry"))
        else:
            say(t("kiwimon.challenge.intro1"), t("kiwimon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(kiwimon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("kiwimon.challenge.won"))
                give(Item.BlueApple)
                give(bits=2500)
                narrator.say(t("kiwimon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(1900, 1250)
                leave()
