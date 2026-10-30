# File City after the ending (§4): the post-game's yearly curse (Machinedramon back in one of the three stations, every
# 20 days) needs a station still standing. With the three roots broken (4.2, 4.3) nothing can grow back: the days are
# never counted up to the curse.
from dw import *
from dw.names import *
from dw.base.file_city_168 import city_168
from ...state import root1, root2, root3

@city_168.on_enter(when=engine.game_beaten and root1 and root2 and root3)
def nothing_grows_back():
    days_since_passed_out.set(0)
    back_dimension_portal.set(0)
