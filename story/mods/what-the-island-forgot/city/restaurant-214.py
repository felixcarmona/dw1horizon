# The Restaurant (214, the first kitchen): Kiwimon, from the Gear Savanna, stays near the food.
from dw import *
from dw.base.restaurant_214 import restaurant
from ..state import new_challenger, CH_KIWIMON

kiwimon = restaurant.npc(Species.Kiwimon, at=(-550, -450), when=recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("I came for one {item Item.Meat} and stayed for the kitchen. Now I cook. I taste everything first, of course.")


# Resident challenges (content/tables/resident-challenges.json): the day Kiwimon is out waiting at its old
# spot, it is not here.
@restaurant.on_enter(when=engine.game_beaten)
def challenger_out_kiwimon():
    if new_challenger == CH_KIWIMON:
        kiwimon.leave()
