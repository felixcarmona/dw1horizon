# 363, the Cold Store: SnowAgumon sells cold food; MudFrigimon (the plains of Mt. Panorama) and SnowGoblimon (Freezeland)
# keep the room frozen.
from dw import *

cold_store = new_screen(363, map="build/what-the-island-forgot-maps/screens/BARR07.MAP")
snowagumon = cold_store.npc(Species.SnowAgumon, at=(0, 100), range=0, when=recruited(Species.SnowAgumon))
mudfrigimon = cold_store.npc(Species.MudFrigimon, at=(-450, -300), range=0, when=recruited(Species.MudFrigimon))
snowgoblimon = cold_store.npc(Species.SnowGoblimon, at=(300, -250), range=0, when=recruited(Species.SnowGoblimon))


@snowagumon.on_talk
def talk():
    say("Brrr, welcome! Everything here was caught or picked this week and kept icy cold.")
    shop(Item.Meat, Item.GiantMeat, Item.DigiTrout, Item.Digisnapper, Item.IceMushrm, Item.PowerIce)


@mudfrigimon.on_talk
def talk():
    say("Mud on the outside, ice on the inside. I sit by the shelves so the fish stay fresh.")


@snowgoblimon.on_talk
def talk():
    say("Freezeland was too far from everything.", "This room is the coldest place in the city. I approve.")
