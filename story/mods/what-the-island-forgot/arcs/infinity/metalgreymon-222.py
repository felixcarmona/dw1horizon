# MetalGreymon's bridge: the south return must pass through the same Infinity hall
# used on the ascent, with its north-side arrival. Keep the original exit walk.
from dw import *
from ...state import root1, root2, root3

bridge = screen(222)

@bridge.on_step(0, when=root1 and root2 and root3)
def back_to_the_dark_engine():
    tamer.walk(-370, -4600, wait=False)
    warp(313, entry=1)

@bridge.on_step(0, when=not (root1 and root2 and root3))
def back_to_the_engine():
    tamer.walk(-370, -4600, wait=False)
    warp(312, entry=1)
