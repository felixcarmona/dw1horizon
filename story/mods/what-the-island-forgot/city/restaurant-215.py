# The Restaurant (215, Digitamamon's kitchen): Kiwimon cooks here too.
from dw import *
from dw.base.restaurant_215 import restaurant, giromon
from ..state import challenger, new_challenger, CH_GIROMON, CH_KIWIMON

kiwimon = restaurant.npc(Species.Kiwimon, at=(-550, -450), behaves_like=giromon, when=recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("Digitamamon's eggs are the best on the island. I would know. I have eaten all of them.")


# Resident challenges (content/tables/resident-challenges.json): the day Giromon is out waiting at its old spot,
# it is not here.
@restaurant.on_enter(when=engine.game_beaten)
def challenger_out_giromon():
    if challenger == CH_GIROMON:
        giromon.leave()


# Resident challenges (content/tables/resident-challenges.json): the day Kiwimon is out waiting at its old
# spot, it is not here.
@restaurant.on_enter(when=engine.game_beaten)
def challenger_out_kiwimon():
    if new_challenger == CH_KIWIMON:
        kiwimon.leave()
