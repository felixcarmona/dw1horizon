# 314, the Root Clearing: two Goblimon from the field next door (MAYO03's).
# Each won fight has a 25 % chance to leave Meat, matching the Goblimon food drop.
# Daily ground food: the three mushrooms of the forest script it replaces.
from dw import *

clearing = new_screen(314, map="build/what-the-island-forgot-maps/screens/ROOT01.MAP")
goblin_east = clearing.npc(Species.Goblimon, at=(1642, 935), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
goblin_south = clearing.npc(Species.Goblimon, at=(750, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)


@clearing.on_enter
def ground_food():
    if random.chance(2):
        spawn_item(Item.Deluxmushrm, at=(-50, -150))
    if random.chance(25):
        spawn_item(Item.Digimushrm, at=(350, -250))
    if random.chance(15):
        spawn_item(Item.Digimushrm, at=(1450, -1350))


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
