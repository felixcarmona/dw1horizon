# Ancient Speedy Region 87, next door to the Ancient Dino Region (79 has no heap for its model): Triceramon pushes a rock. A hard
# fight, the strength of the Dino Region's Tyrannomon. Its home is the Stone Yard (district/stone-yard.py).
from dw import *

region = screen(Screen.ancient_speedy_region_87)
triceramon = region.npc(Species.Triceramon, at=(400, -1200), hp=3100, mp=2800, offense=420, defense=240, speed=200, brain=200, bits=1200,
                        range=0, still=True, when=not recruited(Species.Triceramon))


@triceramon.on_talk
def talk():
    say("It goes there.")
    tamer.say("Why there?")
    say("It goes there.")
    if fight(triceramon) == "won":
        say("You have good shoulders. There is more rock in the city?")
        send_to_city(line="Triceramon joined the city!", species=Species.Triceramon)
