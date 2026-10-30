# The Restaurant (214, the first kitchen): Muchomon (the jungle and the beaches) waits at the tables.
from dw import *
from dw.base.restaurant_214 import restaurant

muchomon = restaurant.npc(Species.Muchomon, at=(-550, -450), when=recruited(Species.Muchomon))


@muchomon.on_talk
def talk():
    say("Welcome, welcome! I came to learn the cooking. For now they let me carry the plates.")
