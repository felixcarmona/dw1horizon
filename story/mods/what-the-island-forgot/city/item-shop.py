# Item Shop 216: the game's residents here who go out as challengers after the ending.
from dw import *
from dw.base.item_shop import shop_, piximon
from ..state import challenger, CH_PIXIMON


# Resident challenges (content/tables/resident-challenges.json): the day Piximon is out waiting at its old
# spot, it is not here.
@shop_.on_enter(when=engine.game_beaten)
def challenger_out_piximon():
    if challenger == CH_PIXIMON:
        piximon.leave()
