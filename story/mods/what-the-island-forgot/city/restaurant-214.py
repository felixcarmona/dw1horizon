# The Restaurant (214, the first kitchen): Kiwimon, from the Gear Savanna, stays near the food.
from dw import *
from dw.base.restaurant_214 import restaurant

kiwimon = restaurant.npc(Species.Kiwimon, at=(-550, -450), when=recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("I came for one {item Item.Meat} and stayed for the kitchen. Now I cook. I taste everything first, of course.")
