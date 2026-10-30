# The Secret Item Shop (217): PlatinumSukamon, the slime that shines (Factorial Town), brings the extra stock.
from dw import *
from dw.base.secret_item_shop import shop_ as secret_shop, ninjamon

platinumsukamon = secret_shop.npc(Species.PlatinumSukamon, at=(550, 450), behaves_like=ninjamon, when=recruited(Species.PlatinumSukamon))


@platinumsukamon.on_talk
def talk():
    say("Shiny things find their way to me. Psst... not everything here is on the list.")
    shop(Item.MediumMP, Item.Restore, Item.Protection, Item.DoubleFlop)
