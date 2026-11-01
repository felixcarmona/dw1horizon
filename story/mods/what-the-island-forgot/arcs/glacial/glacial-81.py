# 81, the Ancient Glacial Region, Brachiomon's meadow (§3.1f): with MasterTyrannomon gone from its post the slow side
# has lost its keeper, and the two Brachiomon have moved on, until the keeper is back (M11 told, bone-field.py).
from dw import *
from dw.base.ancient_glacial_region_81 import brachiomon2, brachiomon3, region
from ...state import post_guided, m11_field

@region.on_enter(when=post_guided and not m11_field)
def moved_on():
    brachiomon2.leave()
    brachiomon3.leave()

@region.on_use(2, when=post_guided and not m11_field)
def nobody_to_greet():
    dws("return;")                # the game's greeting speaks through the Brachiomon that left
