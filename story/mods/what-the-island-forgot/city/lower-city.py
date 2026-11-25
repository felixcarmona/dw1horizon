# Lower File City (script 163, its 24 screens share one cast): the game's residents here who go out as challengers after the ending.
from dw import *
from dw.base.file_city_180 import city_180, elecmon, kunemon, ogremon, shellmon, bakemon, megadramon
from ..state import challenger, CH_ELECMON, CH_KUNEMON, CH_OGREMON, CH_SHELLMON, CH_BAKEMON, CH_MEGADRAMON


# Resident challenges (content/tables/resident-challenges.json): the day one of them is out waiting at its old
# spot, it is not here.
@city_180.on_enter(when=engine.game_beaten)
def challenger_out_residents():
    if challenger == CH_ELECMON:
        elecmon.leave()
    if challenger == CH_KUNEMON:
        kunemon.leave()
    if challenger == CH_OGREMON:
        ogremon.leave()
    if challenger == CH_SHELLMON:
        shellmon.leave()
    if challenger == CH_BAKEMON:
        bakemon.leave()
    if challenger == CH_MEGADRAMON:
        megadramon.leave()
