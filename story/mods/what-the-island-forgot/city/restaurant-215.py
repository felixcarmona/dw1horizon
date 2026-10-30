# The Restaurant (215, Digitamamon's kitchen): Muchomon waits at the tables here too.
from dw import *
from dw.base.restaurant_215 import restaurant, giromon

muchomon = restaurant.npc(Species.Muchomon, at=(-550, -450), behaves_like=giromon, when=recruited(Species.Muchomon))


@muchomon.on_talk
def talk():
    say("Digitamamon's eggs are the best on the island. I am going to learn the secret one day!")
