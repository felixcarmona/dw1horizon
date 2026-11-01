# Mt. Infinity 222, the long hall before the top (the brief's 229 reads no NPC list): Knightmon guards a door to nothing.
# The hardest fight of the residents, above the mountain's wild Digimon. Its home is the Guard House (district/guard-house.py).
from dw import *

hall = screen(Screen.mt_infinity_222)
knightmon = hall.npc(Species.Knightmon, at=(-900, 100), hp=4500, mp=5000, offense=720, defense=380, speed=300, brain=300, bits=2000,
                     range=0, when=not recruited(Species.Knightmon))


@knightmon.on_talk
def talk():
    say("Halt. Nobody passes.")
    tamer.say("Passes what? There's nothing behind you.")
    if fight(knightmon) == "won":
        say("My post is gone, but my oath is not. Name a wall and I will guard it.")
        send_to_city(line="Knightmon joined the city!", species=Species.Knightmon)
