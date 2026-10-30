# 361, the Scrap Office: Geremon buys and sells what the island throws away (the game's buy/sell menu); Goblimon sorts
# the heap. Both came after a beating: Factorial Town or Trash Mountain, and the Great Canyon.
from dw import *

scrap_office = new_screen(361, map="build/what-the-island-forgot-maps/screens/BARR05.MAP")
geremon = scrap_office.npc(Species.Geremon, at=(0, -250), range=0, when=recruited(Species.Geremon))
goblimon = scrap_office.npc(Species.Goblimon, at=(450, -650), range=0, when=recruited(Species.Goblimon))


@geremon.on_talk
def talk():
    say("Junk in, junk out! Sell me what you have two of, buy what somebody else had two of.")
    shop(Item.PortPotty, Item.EnemyRepel, Item.EnemyBell, Item.RestPillow, Item.Bandage)


@goblimon.on_talk
def talk():
    say("Screws here, springs there, the shiny bits to the boss. I lost to you in the canyon,",
        "so I sort scrap now. It is quieter than fighting.")


# Gekomon, freed from the hunters' kennel in the Seam (arcs/seam/kennel.py), keeps the office's radio company.
gekomon = scrap_office.npc(Species.Gekomon, at=(-450, -650), range=0, when=recruited(Species.Gekomon))


@gekomon.on_talk
def talk():
    say("Gero! I remember my name, I remember my horn. Every morning I say both out loud, just in case.")
