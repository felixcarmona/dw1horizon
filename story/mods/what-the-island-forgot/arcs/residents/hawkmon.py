# The Great Canyon Entrance 36 (the bridge's heap cannot hold a fourth model with Birdramon's scene, and no spot on the
# top area keeps a walkable path):
# Hawkmon watches everything and joins if asked. No fight. Its home is Birdra Transport (city/birdra-transport.py).
from dw import *

ledge = screen(Screen.great_canyon_entrance)
hawkmon = ledge.npc(Species.Hawkmon, at=(1200, -450), range=0, still=True, when=not recruited(Species.Hawkmon))


@hawkmon.on_talk
def talk():
    say("I see everything from up here. Nobody ever asks.")
    tamer.say("Then I'm asking. What do you see?")
    say("Far off, File City. New roofs every week, and nobody keeping watch over them.")
    if ask(yes="It needs a lookout", no="It's fine as it is"):
        say("A lookout. Yes. I thought nobody would ever say it.")
        send_to_city(line="Hawkmon joined the city!", species=Species.Hawkmon)
    else:
        say("I'll be here. I see everything, remember.")
