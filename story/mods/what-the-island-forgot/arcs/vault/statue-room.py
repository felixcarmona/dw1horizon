# 97, the Ice Sanctuary's statue room (§3.7, §5.5): once Angemon is awake the voice that woke it ("You who seek my
# soul") is heard again, from under the pedestal, and the pedestal is the way down to the Wall of Hearts (310; 311, the
# melted wall, after "Stay"). The hidden hall 104 is not the way in: the post-game's Machinedramon stands there always.
# Solarmon, a sun frozen in the hall (arcs/residents/README.md; its home: district/power-station.py), joins on either answer.
from dw import *
from dw.base.ice_sanctuary_97 import sanctuary
from ...state import root3

solarmon = sanctuary.npc(Species.Solarmon, at=(800, -600), range=0, when=not recruited(Species.Solarmon))


@solarmon.on_talk
def talk():
    say("The cold forgot me here. Is the sun still up?")
    if ask(yes="It's still up", no="It has set"):
        say("Good. Then I am not the last one.")
    else:
        say("Then somebody has to shine.")
    say("Then I'll go where the lights are.")
    send_to_city(line="Solarmon joined the city!", species=Species.Solarmon)


@sanctuary.on_step(1, when=recruited(Species.Angemon) and not root3)
def the_voice_below():
    narrator.say("From under the pedestal, a cold voice:", "\"Deeper... The hearts are kept deeper...\"")
    tamer.say("There's more down there! Let's go, {partner}!")
    warp(310, entry=0)

@sanctuary.on_step(1, when=root3)
def to_the_door():
    warp(311, entry=0)
