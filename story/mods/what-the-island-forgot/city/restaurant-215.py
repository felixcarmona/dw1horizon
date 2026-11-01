# The Restaurant (215, Digitamamon's kitchen): Kiwimon cooks here too.
from dw import *
from dw.base.restaurant_215 import restaurant, giromon

kiwimon = restaurant.npc(Species.Kiwimon, at=(-550, -450), behaves_like=giromon, when=recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("Digitamamon's eggs are the best on the island. I would know. I have eaten all of them.")
