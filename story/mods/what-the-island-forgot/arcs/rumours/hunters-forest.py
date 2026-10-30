# Native Forest, the big field (screen 2, §3.0): with the word spread, a hunter comes looking for the human at night, from the start.
from dw import *
from dw.base.native_forest_2 import forest
from ...state import rumours_spread

hunter = forest.npc(Species.Gururumon, at=(500, 900), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200,
                    bits=200, range=500, when=clock.hour >= 20 or clock.hour < 5)

@forest.on_enter(when=not rumours_spread)
def not_heard():
    # Presence loads the hunter only at night. Removing an absent script id makes
    # getEntityFromScriptId fall through and corrupts the field's entity table.
    if clock.hour >= 20 or clock.hour < 5:
        hunter.leave()
