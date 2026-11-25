# The Secret Item Shop (217): Phantomon, from the Grey Lord's Mansion's nights, brings the extra stock.
from dw import *
from dw.base.secret_item_shop import shop_ as secret_shop, ninjamon
from ..state import challenger, new_challenger, CH_NINJAMON, CH_PHANTOMON

phantomon = secret_shop.npc(Species.Phantomon, at=(550, 450), behaves_like=ninjamon, when=recruited(Species.Phantomon))


@phantomon.on_talk
def talk():
    say("Their owners no longer need these. Psst... not everything here is on the list.")
    shop(Item.MediumMP, Item.Restore, Item.Protection, Item.DoubleFlop)


# Resident challenges (content/tables/resident-challenges.json): the day one of them is out waiting at its old
# spot, it is not here.
@secret_shop.on_enter(when=engine.game_beaten)
def challenger_out_ninjamon_phantomon():
    if challenger == CH_NINJAMON:
        ninjamon.leave()
    if new_challenger == CH_PHANTOMON:
        phantomon.leave()
