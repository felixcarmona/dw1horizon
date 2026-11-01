# Sewer 163: Clockmon's hands have stopped. Between 11 and 13 the hour looks right to it and it will not listen; at any other
# hour it asks a riddle, as often as needed. No fight. Its home is the Courtyard (district/the-courtyard.py).
from dw import *

sewer = screen(Screen.sewer_163)
clockmon = sewer.npc(Species.Clockmon, at=(-350, -900), range=0, still=True, when=not recruited(Species.Clockmon))


@clockmon.on_talk
def talk():
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
