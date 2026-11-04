# 314, the Root Clearing: two Goblimon from the field next door (MAYO03's). A fight here is the wild one of the field, and
# a win leaves a Blue apple one time in four, the screen's reason to be visited early on (a player's suggestion: a food
# that raises happiness, the thing early partners lack). It sells for 500 bits, so the drop adds about 125 bits a fight to
# the 450 the fight pays, over a fight of a minute or two: no loop (docs/mods/balance.md 6.1, tools/economy_audit.py).
from dw import *

clearing = new_screen(314, map="build/what-the-island-forgot-maps/screens/ROOT01.MAP")
goblin_east = clearing.npc(Species.Goblimon, at=(1642, 935), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
goblin_south = clearing.npc(Species.Goblimon, at=(750, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)


def beaten():
    if random.chance(25):
        give(Item.BlueApple)


@goblin_east.on_talk
def talk():
    if fight(goblin_east) == "won":
        beaten()


@goblin_south.on_talk
def talk():
    if fight(goblin_south) == "won":
        beaten()
