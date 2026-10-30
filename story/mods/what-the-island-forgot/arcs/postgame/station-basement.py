# 66, the Mansion Basement, a post-game station (§4, 4.1): with the Grey Lord at rest (R2) the curse cannot come back
# here; it moves to a station still standing (the fortress, 3, or the ice hall, 1), or nowhere.
from dw import *
from dw.names import *
from dw.base.mansion_basement import basement, machinedramon, analogman
from ...state import root1, root2, root3

@basement.on_enter(when=root2 and back_dimension_portal == 2)
def not_here():
    machinedramon.leave()
    analogman.leave()
    if not root1:
        back_dimension_portal.set(3)
    elif not root3:
        back_dimension_portal.set(1)
    else:
        back_dimension_portal.set(0)
