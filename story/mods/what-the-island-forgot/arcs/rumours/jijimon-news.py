# Jijimon's news (script 210, the library his talk jumps to in both houses): with the rumour spread, Greymon's challenge is
# armed at prosperity 10 instead of the game's 15, here as in the game. His step tiles ring the door and touch the road down
# from the meat farm, and the residents stay away while he is pending: armed anywhere else, he catches any partner there.
from dw import *
from dw.names import *
from ...state import rumours_spread

lib = script(210)                 # no screen of the Screen list

@lib.on_step(0, when=engine.prosperity >= 10 and not greymon_challenge_ready and not recruited(Species.Greymon))
def greymon_heard():
    # The game turns away its own babies and rookies by species here; this also covers the imported ones.
    if partner.level < Level.champion:
        jump_to_script(221, 5)
    if rumours_spread:
        greymon_challenge_ready.set()
