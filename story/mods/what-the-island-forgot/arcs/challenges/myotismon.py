# Grey Lord's Mansion 55: Myotismon, near where it was recruited in the original game; it haunts the arena lobby at night.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MYOTISMON

site = screen(Screen.grey_lords_mansion_55)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Myotismon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
myotismon_challenger = site.npc(Species.Myotismon, at=(300, 1950), bits=300, range=0, still=True, when=challenger == CH_MYOTISMON, alone=challenger == CH_MYOTISMON)



@myotismon_challenger.on_talk
def challenge_myotismon():
    if challenger != CH_MYOTISMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("myotismon.challenge.retry"))
        else:
            say(t("myotismon.challenge.intro1"), t("myotismon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(myotismon_challenger, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("myotismon.challenge.won"))
                give(Item.BlackWing)
                give(bits=4000)
                narrator.say(t("myotismon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(-1250, 950)
                leave()
