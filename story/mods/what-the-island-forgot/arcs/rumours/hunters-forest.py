# Native Forest, the big field (screen 2, §3.0): with the word spread, a hunter comes looking for the human at night, from the start.
from dw import *
from dw.base.native_forest_2 import forest
from ...state import rumours_spread, hunter_noticed, HUNTER_PRESENT_PSTAT

hunter = forest.npc(Species.Gururumon, at=(500, 900), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200,
                    bits=200, range=500, when=clock.hour >= 20 or clock.hour < 5)

@forest.on_enter(when=not rumours_spread)
def not_heard():
    # Presence loads the hunter only at night. Removing an absent script id makes
    # getEntityFromScriptId fall through and corrupts the field's entity table.
    if clock.hour >= 20 or clock.hour < 5:
        hunter.leave()


# Presence is decided on arrival, not when the clock later crosses 20:00.
# p120 is unsaved and unused by these base scripts and the engine.
@forest.on_enter(when=not hunter_noticed)
def remember_hunter():
    pstat(HUNTER_PRESENT_PSTAT).set(0)
    if rumours_spread:
        if clock.hour >= 20 or clock.hour < 5:
            pstat(HUNTER_PRESENT_PSTAT).set(1)


# on_enter runs during the arrival transition. These nearby floor tiles run
# after loading, near the hunter and outside its chase range.
@forest.on_step(0, when=rumours_spread and not hunter_noticed)
def first_sighting():
    if pstat(HUNTER_PRESENT_PSTAT) == 1 and (clock.hour >= 20 or clock.hour < 5):
        hunter_noticed.set()
        tamer.say("That Gururumon isn't from around here... Is it looking for me?")
