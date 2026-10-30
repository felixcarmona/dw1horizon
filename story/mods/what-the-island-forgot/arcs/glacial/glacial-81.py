# 81, the Ancient Glacial Region, Brachiomon's meadow (§3.1f): with MasterTyrannomon gone from its post the slow side
# has lost its keeper, and the two Brachiomon have moved on (they are found on the Bone Field, bone-field.py).
from dw import *
from dw.base.ancient_glacial_region_81 import brachiomon2, brachiomon3, region
from ...state import post_guided

@region.on_enter(when=post_guided)
def moved_on():
    brachiomon2.leave()
    brachiomon3.leave()
