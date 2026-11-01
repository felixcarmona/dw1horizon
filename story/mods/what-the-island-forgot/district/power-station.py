# 360, the Power Station: the battery that lights the Works. Solarmon, thawed out of the Ice Sanctuary, runs it. Wizardmon, from
# the Grey Lord's Mansion, reads Datamon's files by its light: Datamon's and Wizardmon's models do not fit one screen.
from dw import *

power_station = new_screen(360, map="build/what-the-island-forgot-maps/screens/BARR04.MAP")
solarmon = power_station.npc(Species.Solarmon, at=(-300, -450), range=0, when=recruited(Species.Solarmon))
wizardmon = power_station.npc(Species.Wizardmon, at=(400, -500), range=0, when=recruited(Species.Wizardmon))


@solarmon.on_talk
def talk():
    say("The cold forgot me, but the lights did not. I keep the big battery charged",
        "so every lamp in the Works stays lit.")


@wizardmon.on_talk
def talk():
    say("Datamon files what is lost, and I read the files aloud.", "In the Mansion the pages went blank. Here the words stay.")
