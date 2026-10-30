# 81, the Ancient Glacial Region, Brachiomon's meadow (§3.1f): normal speed once the keeper has left its post.
from dw import *
from dw.base.ancient_glacial_region_81 import region
from ...state import post_guided

@region.on_enter(when=post_guided)
def no_slow_time():
    call(Routine.save_clock_speed, arg=0)
