# Sewer 163: Clockmon's hands have stopped. Between 11 and 13 the hour looks right to it and it will not listen; at any other
# hour it asks a riddle, as often as needed. No fight. Its home is the Courtyard (district/the-courtyard.py).
from dw import *
from ...state import challenger, challenge_won, challenge_tried, CHALLENGE_ARMED, CH_CLOCKMON

sewer = screen(Screen.sewer_163)
clockmon = sewer.npc(Species.Clockmon, at=(-350, -900), range=0, still=True, when=not recruited(Species.Clockmon) or trigger(50))


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Clockmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home (district/the-courtyard.py).
@sewer.on_enter(when=recruited(Species.Clockmon) and engine.game_beaten)
def challenge_away_clockmon():
    if challenger != CH_CLOCKMON or challenge_won:
        clockmon.leave()


def challenge_clockmon():
    if challenger != CH_CLOCKMON or challenge_won:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("clockmon.challenge.retry"))
        else:
            say(t("clockmon.challenge.intro1"), t("clockmon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(clockmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("clockmon.challenge.won"))
                give(Item.AutoPilot)
                give(bits=2500)
                narrator.say(t("clockmon.challenge.reward"))
                challenge_won.set()
                run(-1750, -250)
                leave()


@clockmon.on_talk
def talk():
    if recruited(Species.Clockmon):
        challenge_clockmon()
    else:
        say("Tick. Tock. It is always twelve down here.")
        if clock.hour >= 11 and clock.hour <= 13:
            say("You see? Twelve, more or less. Everything is in order.")
        else:
            say("What? Your hour is wrong? Then answer me this.", "If it is always twelve, how many hours pass between one twelve and the next?")
            match choose(a="Twelve hours", b="None at all"):
                case "b":
                    say("None. Then I have been standing still. A city needs a real clock.")
                    send_to_city(line="Clockmon joined the city!", species=Species.Clockmon)
                case _:
                    say("Wrong. Tick. Tock. Think about it. There is plenty of time.")
