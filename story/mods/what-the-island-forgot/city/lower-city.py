# Lower File City (script 163, its 24 screens share one cast): the game's residents here who go out as challengers after the ending.
from dw import *
from dw.base.file_city_180 import city_180, elecmon
from ..state import challenger, challenge_won, CH_ELECMON


# Resident challenges (content/tables/resident-challenges.json): the day Elecmon is out waiting at its old
# spot, it is not here.
@city_180.on_enter(when=engine.game_beaten)
def challenger_out_elecmon():
    if challenger == CH_ELECMON and not challenge_won:
        elecmon.leave()
