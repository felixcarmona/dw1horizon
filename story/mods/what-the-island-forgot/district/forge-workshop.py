# 362, the Forge: Candlemon, relit in the Lava Cave, keeps the fire and sells the disks and chips it forges.
from dw import *

forge_workshop = new_screen(362, map="build/what-the-island-forgot-maps/screens/BARR06.MAP")
candlemon = forge_workshop.npc(Species.Candlemon, at=(0, -250), range=0, when=recruited(Species.Candlemon))


@candlemon.on_talk
def talk():
    say("In the Lava Cave I nearly went out. Here I burn all day and make things that make you stronger.")
    shop(Item.OffDisk, Item.DefDisk, Item.HispeedDsk, Item.OffChip, Item.DefChip)
