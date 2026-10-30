# 360, the Power Station: the battery that lights the Works. Tentomon (Beetle Land) runs it; Yanmamon, beaten in the
# swamps, came for the hum of the coils. (A third model does not fit the room's heap: SandYanmamon lives in the Courtyard.)
from dw import *

power_station = new_screen(360, map="build/what-the-island-forgot-maps/screens/BARR04.MAP")
tentomon = power_station.npc(Species.Tentomon, at=(-300, -450), range=0, when=recruited(Species.Tentomon))
yanmamon = power_station.npc(Species.Yanmamon, at=(400, -500), range=0, when=recruited(Species.Yanmamon))


@tentomon.on_talk
def talk():
    say("Bzzt! Beetle Land was all wings and no wires. Here I keep the big battery charged",
        "so every lamp in the Works stays lit.")


@yanmamon.on_talk
def talk():
    say("Hmmmmm... the coils sing all day. It sounds like the swamp at dusk. I like it here.")

