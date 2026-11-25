# Jijimon's house (206): Monzaemon's home in the city.
from dw import *
from dw.base.jijimons_house_206 import house, monzaemon
from ..state import challenger, CH_MONZAEMON


# Resident challenges (content/tables/resident-challenges.json): the day Monzaemon is out waiting at its old spot,
# it is not here.
@house.on_enter(when=engine.game_beaten)
def challenger_out_monzaemon():
    if challenger == CH_MONZAEMON:
        monzaemon.leave()
