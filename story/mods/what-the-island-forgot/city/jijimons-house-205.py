# Jijimon's house, room 10 (205): Soulmon (Overdell's graveyard, at night) reads the old letters of the stones.
from dw import *
from dw.base.jijimons_house_205 import house, tokomon

soulmon = house.npc(Species.Soulmon, at=(400, -400), behaves_like=tokomon, when=recruited(Species.Soulmon))


@soulmon.on_talk
def talk():
    say("Ooooh... the old stones of the island have letters nobody reads anymore.",
        "I read them. Ghosts have time.")
