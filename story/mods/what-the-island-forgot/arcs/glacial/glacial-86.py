# The crater cleft is a way back from the Bone Field, never a first entrance.
from dw import *
from dw.base.ancient_speedy_region_86 import region
from ...state import bone_field_visited

@region.on_step(0, when=bone_field_visited)
def back_to_the_field():
    warp(306, entry=1)

@region.on_step(0, when=not bone_field_visited)
def narrow_crack():
    tamer.say("The crack is too narrow... I can't get through.")
    tamer.walk(150, 1050)
