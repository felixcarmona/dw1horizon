# 361, the Scrap Office: Datamon, from Factorial Town, buys and sells what the island throws away (the game's buy/sell menu).
# Pumpkinmon, from the Toy Mansion's nights, sells the hot vegetables nobody else stocks: the Item Shop 216 has no heap for it.
from dw import *

scrap_office = new_screen(361, map="build/what-the-island-forgot-maps/screens/BARR05.MAP")
datamon = scrap_office.npc(Species.Datamon, at=(0, -250), range=0, when=recruited(Species.Datamon))
pumpkinmon = scrap_office.npc(Species.Pumpkinmon, at=(450, -650), range=0, when=recruited(Species.Pumpkinmon))


@datamon.on_talk
def talk():
    say("Everything lost ends up in a file. Sell me what you have two of, buy what somebody else had two of.")
    shop(Item.PortPotty, Item.EnemyRepel, Item.EnemyBell, Item.RestPillow, Item.Bandage)


@pumpkinmon.on_talk
def talk():
    say("Trick or treat? Here it is always treat, if you can pay.", "Hot roots! Your partner will run twice as fast!")
    shop(Item.Supercarrot, Item.HawkRadish, Item.SpinyGreen)
