# File City after the ending (§4, 4.1): with the Vault melted (R3) the curse cannot take the ice hall (station 1, where
# the game's script 187 sends the tamer); it moves to a station still standing, or nowhere. (The hall itself, screen
# 104, holds Machinedramon at every hour; nothing sends the tamer there once the station is gone.)
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168
from ...state import root1, root2, root3

@city_168.on_enter(when=engine.game_beaten and root3 and back_dimension_portal == 1)
def not_the_ice():
    if not root1:
        back_dimension_portal.set(3)
    elif not root2:
        back_dimension_portal.set(2)
    else:
        back_dimension_portal.set(0)
