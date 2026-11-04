# 314, the Root Clearing: two Goblimon from the field next door (MAYO03's).
# Each won fight has a 25 % chance to leave Meat, matching the Goblimon food drop.
from dw import *

clearing = new_screen(314, map="build/what-the-island-forgot-maps/screens/ROOT01.MAP")
goblin_east = clearing.npc(Species.Goblimon, at=(1642, 935), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
goblin_south = clearing.npc(Species.Goblimon, at=(750, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)


def beaten():
    if random.chance(25):
        give(Item.Meat)


@goblin_east.on_talk
def talk():
    if fight(goblin_east) == "won":
        beaten()


@goblin_south.on_talk
def talk():
    if fight(goblin_south) == "won":
        beaten()
