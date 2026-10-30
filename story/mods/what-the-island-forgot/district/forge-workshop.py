# 362, the Forge: Tekkamon (from the Underground Lab) forges the disks and chips he sells; BlueMeramon keeps the fire and
# Flarerizamon, from the foot of Mt. Panorama, works the bellows.
from dw import *

forge_workshop = new_screen(362, map="build/what-the-island-forgot-maps/screens/BARR06.MAP")
tekkamon = forge_workshop.npc(Species.Tekkamon, at=(0, -250), range=0, when=recruited(Species.Tekkamon))
bluemeramon = forge_workshop.npc(Species.BlueMeramon, at=(500, -400), range=0, when=recruited(Species.BlueMeramon))
flarerizamon = forge_workshop.npc(Species.Flarerizamon, at=(-450, -650), range=0, when=recruited(Species.Flarerizamon))


@tekkamon.on_talk
def talk():
    say("Clang! Clang! The lab built me to fix machines. Now I make things that make you stronger.")
    shop(Item.OffDisk, Item.DefDisk, Item.HispeedDsk, Item.OffChip, Item.DefChip)


@bluemeramon.on_talk
def talk():
    say("A blue flame burns hotter than a red one. That is why the iron here comes out so hard.")


@flarerizamon.on_talk
def talk():
    say("Puff, puff... I pump the bellows all day.", "At the foot of the mountain I only burnt grass!")
