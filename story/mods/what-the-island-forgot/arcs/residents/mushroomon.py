# Mt. Panorama's Spore Area 21: Mushroomon sneezes spores at whoever passes. A fight at the mountain's wild strength; its
# home is the Clinic (city/centar-clinic.py).
from dw import *

area = screen(Screen.mt_panorama_spore_area_21)
mushroomon = area.npc(Species.Mushroomon, at=(-450, 100), hp=1200, mp=2000, offense=300, defense=150, speed=120, brain=100, bits=300,
                      range=0, when=not recruited(Species.Mushroomon))


@mushroomon.on_talk
def talk():
    say("Ah... ah... AH-CHOO!")
    tamer.say("Cough, cough! What is all this dust?")
    say("Spores. Nobody stays on their feet for long around me.")
    if fight(mushroomon) == "won":
        say("You're not sick. Interesting. I could learn medicine from you.")
        send_to_city(line="Mushroomon joined the city!", species=Species.Mushroomon)
