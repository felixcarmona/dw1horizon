# Treasure Hunt (209): Gabumon's home in the city.
from dw import *
from dw.base.treasure_hunt import hunt, gabumon
from ..state import challenger, challenge_won, CH_GABUMON


# Resident challenges (content/tables/resident-challenges.json): the day Gabumon is out waiting at its old spot,
# it is not here.
@hunt.on_enter(when=engine.game_beaten)
def challenger_out_gabumon():
    if challenger == CH_GABUMON and not challenge_won:
        gabumon.leave()
