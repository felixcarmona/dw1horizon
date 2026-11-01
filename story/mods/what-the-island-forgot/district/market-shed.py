# 364, the Market Shed: Tapirmon, woken at Dragon Eye Lake, runs the stall (fruit and roots from all over the island) and
# sells a dream or two with them.
from dw import *

market_shed = new_screen(364, map="build/what-the-island-forgot-maps/screens/BARR08.MAP")
tapirmon = market_shed.npc(Species.Tapirmon, at=(0, 100), range=0, when=recruited(Species.Tapirmon))


@tapirmon.on_talk
def talk():
    say("Fresh from every corner of the island! The dreams are free. The fruit is not.")
    shop(Item.Digipine, Item.BlueApple, Item.RedBerry, Item.SweetNut, Item.OrangeBana, Item.Supercarrot)
