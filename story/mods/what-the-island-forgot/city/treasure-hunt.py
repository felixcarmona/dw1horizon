# The Treasure Hunt (209): Akatorimon, from Misty Trees, is looking for "something shiny".
from dw import *
from dw.base.treasure_hunt import hunt, gabumon

# The back counter is a disconnected walkable island; stand on the customer floor.
akatorimon = hunt.npc(Species.Akatorimon, at=(-550, -350), behaves_like=gabumon, when=recruited(Species.Akatorimon))


@akatorimon.on_talk
def talk():
    say("Something shiny is buried somewhere on this island.", "Drimogemon digs, I point. Cluck!")
