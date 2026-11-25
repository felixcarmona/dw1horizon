# Item Keeper 211: the game's residents here who go out as challengers after the ending.
from dw import *
from dw.base.item_keeper import keeper, nanimon
from ..state import challenger, CH_NANIMON


# Resident challenges (content/tables/resident-challenges.json): the day Nanimon is out waiting at its old
# spot, it is not here.
@keeper.on_enter(when=engine.game_beaten)
def challenger_out_nanimon():
    if challenger == CH_NANIMON:
        nanimon.leave()
