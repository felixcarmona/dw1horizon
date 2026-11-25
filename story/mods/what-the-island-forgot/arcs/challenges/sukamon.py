# Trash Mountain 164: Sukamon, near where it was recruited in the original game; it runs the sweep service.
from dw import *
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_SUKAMON

site = screen(Screen.trash_mountain_164)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Sukamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.
sukamon = site.npc(Species.Sukamon, at=(400, 850), bits=300, range=0, still=True, when=challenger == CH_SUKAMON, alone=challenger == CH_SUKAMON)



@sukamon.on_talk
def challenge_sukamon():
    if challenger != CH_SUKAMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("sukamon.challenge.retry"))
        else:
            say(t("sukamon.challenge.intro1"), t("sukamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(sukamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("sukamon.challenge.won"))
                give(Item.PortPotty)
                give(bits=2500)
                narrator.say(t("sukamon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(400, 3350)
                leave()
