# 360, the Power Station: the battery that lights the Works. Solarmon, thawed out of the Ice Sanctuary, runs it.
from dw import *

power_station = new_screen(360, map="build/what-the-island-forgot-maps/screens/BARR04.MAP")
solarmon = power_station.npc(Species.Solarmon, at=(-300, -450), range=0, when=recruited(Species.Solarmon))


@solarmon.on_talk
def talk():
    say("The cold forgot me, but the lights did not. I keep the big battery charged",
        "so every lamp in the Works stays lit.")
