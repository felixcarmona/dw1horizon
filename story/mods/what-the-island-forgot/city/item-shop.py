# The Item Shop (216): Pumpkinmon, from Toy Town's nights, sells the hot vegetables nobody else stocks.
from dw import *
from dw.base.item_shop import shop_ as item_shop, punimon

pumpkinmon = item_shop.npc(Species.Pumpkinmon, at=(-900, -500), behaves_like=punimon, when=recruited(Species.Pumpkinmon))


@pumpkinmon.on_talk
def talk():
    say("Trick or treat? Here it is always treat, if you can pay.", "Hot roots! Your partner will run twice as fast!")
    shop(Item.Supercarrot, Item.HawkRadish, Item.SpinyGreen)
