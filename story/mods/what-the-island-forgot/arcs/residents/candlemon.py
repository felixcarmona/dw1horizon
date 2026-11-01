# Lava Cave 30: Candlemon, its flame nearly out. A friendly fight, weaker than the zone's. Its home is the Forge
# (district/forge-workshop.py).
from dw import *

cave = screen(Screen.lava_cave_30)
candlemon = cave.npc(Species.Candlemon, at=(-1050, 900), hp=700, mp=1200, offense=200, defense=90, speed=80, brain=80, bits=200,
                     range=0, when=not recruited(Species.Candlemon))


@candlemon.on_talk
def talk():
    say("Too hot to die, too small to burn.")
    say("Give me a good fight. It's the only thing that still lights me.")
    if fight(candlemon) == "won":
        say("That lit me up! Have you got a forge?")
        send_to_city(line="Candlemon joined the city!", species=Species.Candlemon)
