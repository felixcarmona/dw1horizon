# 364, the Market Shed: Gotsumon runs the stall (fruit and roots from all over the island); ShimaUnimon hauls the
# crates and ClearAgumon, out of the Toy Mansion, minds the scales nobody can see him standing at.
from dw import *

market_shed = new_screen(364, map="build/what-the-island-forgot-maps/screens/BARR08.MAP")
gotsumon = market_shed.npc(Species.Gotsumon, at=(0, 100), range=0, when=recruited(Species.Gotsumon))
shimaunimon = market_shed.npc(Species.ShimaUnimon, at=(-500, -350), range=0, when=recruited(Species.ShimaUnimon))
clearagumon = market_shed.npc(Species.ClearAgumon, at=(400, -150), range=0, when=recruited(Species.ClearAgumon))


@gotsumon.on_talk
def talk():
    say("Rocks don't eat, but you do! Fresh from every corner of the island.")
    shop(Item.Digipine, Item.BlueApple, Item.RedBerry, Item.SweetNut, Item.OrangeBana, Item.Supercarrot)


@shimaunimon.on_talk
def talk():
    say("I carry the crates up from the savanna roads. My stripes are good for business.")


@clearagumon.on_talk
def talk():
    say("Oh! You can see me? Most customers walk right through. I watch the scales.")
