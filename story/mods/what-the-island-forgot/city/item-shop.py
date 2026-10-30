# The Item Shop (216): RedVegiemon, beaten in the jungles, sells the hot vegetables nobody else stocks.
from dw import *
from dw.base.item_shop import shop_ as item_shop, punimon

redvegiemon = item_shop.npc(Species.RedVegiemon, at=(-900, -500), behaves_like=punimon, when=recruited(Species.RedVegiemon))


@redvegiemon.on_talk
def talk():
    say("Hot, hot, hot! Spicy roots from the jungle. Your partner will run twice as fast!")
    shop(Item.Supercarrot, Item.HawkRadish, Item.SpinyGreen)
