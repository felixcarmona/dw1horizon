# Grey Lord's Mansion 59, the dead-end room off the hall (the brief's 54 reads no NPC list): Wizardmon reads a book whose
# pages have gone blank. It joins once the city has grown (prosperity 20: recruits only add to it, so it is no dead end).
# Its home is the Power Station (district/power-station.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_WIZARDMON

room = screen(Screen.grey_lords_mansion_59)
wizardmon = room.npc(Species.Wizardmon, at=(0, 300), range=0, still=True, when=not recruited(Species.Wizardmon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Wizardmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/power-station.py).
@room.on_enter(when=recruited(Species.Wizardmon) and engine.game_beaten)
def challenge_away_wizardmon():
    if challenger != CH_WIZARDMON or challenge_won:
        wizardmon.leave()


def challenge_wizardmon():
    if challenger != CH_WIZARDMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("wizardmon.challenge.retry"))
        else:
            say(t("wizardmon.challenge.intro1"), t("wizardmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(wizardmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("wizardmon.challenge.won"))
                give(Item.BrainChip)
                give(bits=2500)
                narrator.say(t("wizardmon.challenge.reward"))
                challenge_won.set()
                run(-950, -1400)
                leave()


@wizardmon.on_talk
def talk():
    if recruited(Species.Wizardmon):
        challenge_wizardmon()
    else:
        say("The words are leaving. I need someone who still remembers things.")
        if engine.prosperity >= 20:
            say("A whole city that remembers you? Then I will read there.")
            send_to_city(line="Wizardmon joined the city!", species=Species.Wizardmon)
        else:
            say("Come back when you have read more of this island.")
