# Freezeland 94 (the brief's 92 reads no NPC list): Mammothmon has stood here since before the ice. An end-game fight, the
# strength of Mt. Infinity's wild Digimon. Its home is the Cold Store (district/cold-store.py).
from dw import *

field = screen(Screen.freezeland_94)
mammothmon = field.npc(Species.Mammothmon, at=(0, 450), hp=3600, mp=4000, offense=640, defense=340, speed=250, brain=200, bits=1500,
                       range=0, still=True, when=not recruited(Species.Mammothmon))


@mammothmon.on_talk
def talk():
    say("I have stood here since before the ice.")
    if fight(mammothmon) == "won":
        say("Warm hands. I had forgotten.")
        send_to_city(line="Mammothmon joined the city!", species=Species.Mammothmon)
