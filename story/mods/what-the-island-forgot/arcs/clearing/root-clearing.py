# 314, the Root Clearing: two Goblimon from the field next door (MAYO03's). A fight here is the wild one of the field, and
# a win leaves a Blue apple one time in four. Daily ground food gives another reason to visit early: a Blue apple
# raises happiness. It sells for 500 bits, so the battle drop adds about 125 bits a fight to
# the 450 the fight pays, over a fight of a minute or two: no loop (docs/mods/balance.md 6.1, tools/economy_audit.py).
from dw import *

clearing = new_screen(314, map="build/what-the-island-forgot-maps/screens/ROOT01.MAP")
goblin_east = clearing.npc(Species.Goblimon, at=(1642, 935), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)
goblin_south = clearing.npc(Species.Goblimon, at=(750, -850), hp=400, mp=800, offense=160, defense=70, speed=50, brain=50, bits=300)


@clearing.on_enter
def ground_food():
    if random.chance(2):
        spawn_item(Item.Deluxmushrm, at=(-50, -150))
    if random.chance(25):
        spawn_item(Item.Digimushrm, at=(350, -50))
    if random.chance(15):
        spawn_item(Item.Digimushrm, at=(1450, -1350))
    if random.chance(30):
        spawn_item(Item.BlueApple, at=(-550, -750))


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
