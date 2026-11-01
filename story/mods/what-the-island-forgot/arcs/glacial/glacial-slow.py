# 80, the Ancient Glacial Region (§3.1f): the slow side without its keeper (post_guided, until M11) runs at normal speed; the
# entrance (79, dino-79.dws) no longer slows the clock, and this screen keeps it so for a tamer who comes back from the
# meadow or the path.
from dw import *
from dw.base.ancient_glacial_region_80 import region
from ...state import post_guided, m11_field

@region.on_enter(when=post_guided and not m11_field)
def no_slow_time():
    call(Routine.save_clock_speed, arg=0)
