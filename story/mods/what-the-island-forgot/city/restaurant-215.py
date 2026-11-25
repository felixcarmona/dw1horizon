# The Restaurant (215, Digitamamon's kitchen): Kiwimon cooks here too.
from dw import *
from dw.base.restaurant_215 import restaurant, giromon
from ..state import challenger, challenge_won, CH_GIROMON

kiwimon = restaurant.npc(Species.Kiwimon, at=(-550, -450), behaves_like=giromon, when=recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("Digitamamon's eggs are the best on the island. I would know. I have eaten all of them.")


# Resident challenges (content/tables/resident-challenges.json): the day Giromon is out waiting at its old spot,
# it is not here.
@restaurant.on_enter(when=engine.game_beaten)
def challenger_out_giromon():
    if challenger == CH_GIROMON and not challenge_won:
        giromon.leave()
