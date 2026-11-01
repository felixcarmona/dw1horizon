# 81, the Ancient Glacial Region, Brachiomon's meadow (§3.1f): normal speed while the keeper is away from its post.
from dw import *
from dw.base.ancient_glacial_region_81 import region
from ...state import post_guided, m11_field

@region.on_enter(when=post_guided and not m11_field)
def no_slow_time():
    call(Routine.save_clock_speed, arg=0)
