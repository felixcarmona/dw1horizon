# 363, the Cold Store: Mammothmon, who stood in Freezeland since before the ice, keeps the room cold and sells cold food.
from dw import *

cold_store = new_screen(363, map="build/what-the-island-forgot-maps/screens/BARR07.MAP")
mammothmon = cold_store.npc(Species.Mammothmon, at=(0, 100), range=0, when=recruited(Species.Mammothmon))


@mammothmon.on_talk
def talk():
    say("I carried the ice in on my back. Everything here was caught or picked this week and kept cold.")
    shop(Item.Meat, Item.GiantMeat, Item.DigiTrout, Item.Digisnapper, Item.IceMushrm, Item.PowerIce)
