# 254, Megadramon's terrace on Mt. Infinity (script 198): the way on (step trigger 0, to MetalGreymon's bridge, 222)
# now passes through the Infinity Engine room (312; 313, the dark one, once the three roots are broken). After
# Devimon's shortcut the climb was skipped: Megadramon is not here.
from dw import *
from ...state import root1, root2, root3, shortcut_taken

lib = script(198)                 # the library screen 254 runs (no screen of the Screen list)
megadramon = entity(11)           # its slot 6

@lib.on_step(0, when=root1 and root2 and root3)
def into_the_dark_engine():
    tamer.walk(-2748, 3453, wait=False)
    warp(313, entry=0)

@lib.on_step(0, when=not (root1 and root2 and root3))
def into_the_engine():
    tamer.walk(-2748, 3453, wait=False)
    warp(312, entry=0)

@lib.on_enter(when=shortcut_taken)
def nobody_here():
    megadramon.leave()
