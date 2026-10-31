# The Drain (356): the original first entry to Factorial Town is Whamon's ferry
# (T224); the land door later accepts T328. Keep both original ways of opening
# the town, and leave the south exit to the Heart of the Mine unconditional.
from dw import *
from dw.names import *

drain = new_screen(356, map="build/what-the-island-forgot-maps/screens/MINE20.MAP")
drain_gururumon = drain.npc(Species.Gururumon, at=(-100, -300), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400, range=800)

@drain.on_step(0, when=recruited(Species.Whamon) or factorial_town_reopened)
def into_the_sewer():
    warp(Screen.sewer_220, entry=1)

@drain.on_step(0, when=not recruited(Species.Whamon) and not factorial_town_reopened)
def sealed_drain():
    tamer.say("The drain's sealed. We'll have to reach the town another way first.")
    tamer.walk(-467, 1274)
