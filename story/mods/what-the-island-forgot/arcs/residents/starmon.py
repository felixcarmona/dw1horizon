# Mt. Panorama's Spore Area 233: Starmon looks up at where it fell from, and fights for the fun of it, at the mountain's
# wild strength. Its home is the Container House (district/container-house.py).
from dw import *

ledge = screen(Screen.mt_panorama_spore_area_233)
starmon = ledge.npc(Species.Starmon, at=(1000, -1000), hp=1200, mp=2000, offense=300, defense=150, speed=130, brain=100, bits=300,
                    range=0, when=not recruited(Species.Starmon))


@starmon.on_talk
def talk():
    say("Do you know how far I've fallen?")
    say("Never mind. Want to see some stars?")
    if fight(starmon) == "won":
        say("A hit like that! The city must be full of stars.")
        send_to_city(line="Starmon joined the city!", species=Species.Starmon)
