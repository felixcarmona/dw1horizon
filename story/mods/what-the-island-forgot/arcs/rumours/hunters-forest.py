# Native Forest, the big field (screen 2, §3.0): with the word spread, a hunter comes looking for the human at night, from the start.
from dw import *
from dw.base.native_forest_2 import forest
from ...state import rumours_spread, hunter_noticed, HUNTER_PRESENT_PSTAT

hunter = forest.npc(Species.Gururumon, slot=5, at=(500, 900), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200,
                    bits=200, range=500, when=clock.hour >= 20 or clock.hour < 5)

@forest.on_enter(when=not rumours_spread)
def not_heard():
    # Presence loads the hunter only at night. Removing an absent script id makes
    # getEntityFromScriptId fall through and corrupts the field's entity table.
    if clock.hour >= 20 or clock.hour < 5:
        hunter.leave()


# Presence is decided on arrival, not when the clock later crosses 20:00.
# The model stays loaded while this first actor waits to enter near the tamer.
# Both removal paths require the night presence to have spawned a live script id.
@forest.on_enter(when=not hunter_noticed)
def remember_hunter():
    pstat(HUNTER_PRESENT_PSTAT).set(0)
    if rumours_spread:
        if clock.hour >= 20 or clock.hour < 5:
            pstat(HUNTER_PRESENT_PSTAT).set(1)
            hunter.leave()


# on_enter runs during the arrival transition. These nearby floor tiles run
# after loading, outside its chase range. Respawn from the already-loaded model
# so a long patrol cannot put the hunter off-screen before its first line.
@forest.on_step(0, when=rumours_spread and not hunter_noticed)
def first_sighting():
    if pstat(HUNTER_PRESENT_PSTAT) == 1 and (clock.hour >= 20 or clock.hour < 5):
        hunter_noticed.set()
        spawn(Species.Gururumon, slot=5)
        tamer.say("That Gururumon isn't from around here... Is it looking for me?")
