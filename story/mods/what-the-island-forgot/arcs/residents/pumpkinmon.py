# The Toy Mansion's hall 147, at night only (Toy Town 144 has no heap for a fourth model): Pumpkinmon wants a game. A fight at
# Toy Town's strength. Its home is the Item Shop (city/item-shop.py).
from dw import *

hall = screen(Screen.toy_mansion_147)
pumpkinmon = hall.npc(Species.Pumpkinmon, at=(-1300, 700), hp=1400, mp=2000, offense=260, defense=130, speed=120, brain=100, bits=300,
                      range=0, still=True, when=not recruited(Species.Pumpkinmon) and clock.hour >= 20)


@pumpkinmon.on_talk
def talk():
    say("Trick or treat! No? Then a game.")
    if fight(pumpkinmon) == "won":
        say("You don't scare easily. Good. I need customers like that.")
        send_to_city(line="Pumpkinmon joined the city!", species=Species.Pumpkinmon)
