# 361, the Scrap Office: Datamon, from Factorial Town, buys and sells what the island throws away (the game's buy/sell menu).
from dw import *

scrap_office = new_screen(361, map="build/what-the-island-forgot-maps/screens/BARR05.MAP")
datamon = scrap_office.npc(Species.Datamon, at=(0, -250), range=0, when=recruited(Species.Datamon))


@datamon.on_talk
def talk():
    say("Everything lost ends up in a file. Sell me what you have two of, buy what somebody else had two of.")
    shop(Item.PortPotty, Item.EnemyRepel, Item.EnemyBell, Item.RestPillow, Item.Bandage)
