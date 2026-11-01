# Ancient Speedy Region 85, the quiet end of the valley (the brief's 84 reads no NPC list): Armadillomon, half buried, is
# sure of its treasure and will not share the spot without a tussle. Its home is the Courtyard (district/the-courtyard.py).
from dw import *

valley = screen(Screen.ancient_speedy_region_85)
armadillomon = valley.npc(Species.Armadillomon, at=(-600, 800), hp=1800, mp=2000, offense=300, defense=180, speed=150, brain=100, bits=600,
                          range=0, still=True, when=not recruited(Species.Armadillomon))


@armadillomon.on_talk
def talk():
    say("Treasure! I swear there's treasure right under here!")
    say("This is my hole! Find your own!")
    if fight(armadillomon) == "won":
        say("Nothing down there but more dirt anyway.")
        say("Somebody in the city must be hiding better things.")
        send_to_city(line="Armadillomon joined the city!", species=Species.Armadillomon)
