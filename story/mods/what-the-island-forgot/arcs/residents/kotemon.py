# Ogre Fortress 45, the gate yard (the brief's 130 reads no NPC list): Kotemon trains alone. A fight at the fortress's
# strength, with no running away. Its home is the Arena lobby (city/arena-lobby.py).
from dw import *

yard = screen(Screen.ogre_fortress_45)
kotemon = yard.npc(Species.Kotemon, at=(1000, 850), hp=1200, mp=1600, offense=400, defense=210, speed=120, brain=120, bits=300,
                   range=0, still=True, when=not recruited(Species.Kotemon))


@kotemon.on_talk
def talk():
    say("One more thousand swings.")
    if fight(kotemon, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: Kotemon goes on swinging
    say("Teach me? No, I'll teach you. Where's the Arena?")
    send_to_city(line="Kotemon joined the city!", species=Species.Kotemon)
