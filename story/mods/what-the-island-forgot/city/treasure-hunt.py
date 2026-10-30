# The Treasure Hunt (209): Akatorimon, from Misty Trees, is looking for "something shiny".
from dw import *
from dw.base.treasure_hunt import hunt, gabumon

akatorimon = hunt.npc(Species.Akatorimon, at=(-150, 850), behaves_like=gabumon, when=recruited(Species.Akatorimon))


@akatorimon.on_talk
def talk():
    say("Something shiny is buried somewhere on this island.", "Drimogemon digs, I point. Cluck!")
