# Gear Savanna (screen 70, §3.0): with the word spread, a hunter comes looking for the human at night, from the start.
from dw import *
from dw.base.gear_savanna_70 import savanna
from ...state import rumours_spread

hunter = savanna.npc(Species.Gururumon, at=(500, 200), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200,
                     bits=200, range=500, when=clock.hour >= 20 or clock.hour < 5)

@savanna.on_enter(when=not rumours_spread)
def not_heard():
    # Presence loads the hunter only at night. Removing an absent script id makes
    # getEntityFromScriptId fall through and corrupts the field's entity table.
    if clock.hour >= 20 or clock.hour < 5:
        hunter.leave()
