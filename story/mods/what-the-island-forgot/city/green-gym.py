# Green Gym 112: the game's residents here who go out as challengers after the ending.
from dw import *
from dw.base.green_gym import gym, kabuterimon
from ..state import challenger, challenge_won, CH_KABUTERIMON


# Resident challenges (content/tables/resident-challenges.json): the day Kabuterimon is out waiting at its old
# spot, it is not here.
@gym.on_enter(when=engine.game_beaten)
def challenger_out_kabuterimon():
    if challenger == CH_KABUTERIMON and not challenge_won:
        kabuterimon.leave()
