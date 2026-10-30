# 47, the Ogre Fortress's human room, a post-game station (§4, 4.1): with the Motor broken (R1) the curse cannot come
# back here; it moves to a station still standing (the basement, 2, or the ice hall, 1), or nowhere.
from dw import *
from dw.names import *
from dw.base.ogre_fortress_47 import fortress, machinedramon, analogman
from ...state import root1, root2, root3

@fortress.on_enter(when=root1 and back_dimension_portal == 3)
def not_here():
    from_this_station()

def from_this_station():
    machinedramon.leave()
    analogman.leave()
    if not root2:
        back_dimension_portal.set(2)
    elif not root3:
        back_dimension_portal.set(1)
    else:
        back_dimension_portal.set(0)
