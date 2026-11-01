# 361, the Scrap Office: Datamon, from Factorial Town, buys and sells what the island throws away (the game's buy/sell menu).
# Wizardmon, from the Grey Lord's Mansion, reads Datamon's files aloud.
from dw import *

scrap_office = new_screen(361, map="build/what-the-island-forgot-maps/screens/BARR05.MAP")
datamon = scrap_office.npc(Species.Datamon, at=(0, -250), range=0, when=recruited(Species.Datamon))
wizardmon = scrap_office.npc(Species.Wizardmon, at=(450, -650), range=0, when=recruited(Species.Wizardmon))


@datamon.on_talk
def talk():
    say("Everything lost ends up in a file. Sell me what you have two of, buy what somebody else had two of.")
    shop(Item.PortPotty, Item.EnemyRepel, Item.EnemyBell, Item.RestPillow, Item.Bandage)


@wizardmon.on_talk
def talk():
    say("Datamon files what is lost, and I read the files aloud.", "In the Mansion the pages went blank. Here the words stay.")
