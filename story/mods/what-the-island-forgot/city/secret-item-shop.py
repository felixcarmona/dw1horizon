# The Secret Item Shop (217): Phantomon, from the Grey Lord's Mansion's nights, brings the extra stock.
from dw import *
from dw.base.secret_item_shop import shop_ as secret_shop, ninjamon

phantomon = secret_shop.npc(Species.Phantomon, at=(550, 450), behaves_like=ninjamon, when=recruited(Species.Phantomon))


@phantomon.on_talk
def talk():
    say("Their owners no longer need these. Psst... not everything here is on the list.")
    shop(Item.MediumMP, Item.Restore, Item.Protection, Item.DoubleFlop)
