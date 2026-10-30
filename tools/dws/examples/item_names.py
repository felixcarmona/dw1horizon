# The item lists with long names (docs/mods/font.md), all from the Item Keeper (screen 211): its counter
# offers the keeper, Mojyamon's trades (page 0: Digimushroom, Supercarrot, Happymushroom for Medium Recovery, Omnipotent
# Floppy, Hair Grower) and a battle with the keeper (the battle's item list); a chest in front of the entrance holds a
# Deluxe Mushroom (the "Got X" box). Built into a disc with build-full.sh's EXTRA_STORY.
from dw import *
from dw.base.item_keeper import keeper, agumon

chest_taken = flag()

@keeper.on_enter
def enter():
    spawn_chest(Item.Deluxmushrm, at=(0, -332), opened=chest_taken)

@keeper.on_use(1)
def counter():
    match choose(keep="Keeper", trade="Trades", fight="Fight"):
        case "keep":
            call(Routine.item_keeper, arg=5)
        case "trade":
            pstat(249).set(0)
            call(Routine.mojyamon_trade)
        case "fight":
            fight(agumon)
