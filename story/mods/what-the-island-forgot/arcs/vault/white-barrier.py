# 92, Freezeland, the white barrier (§3.7): with the Wall of Hearts melted (R3) the "mysterious white power" is gone and
# any partner may go on into Freezeland. The game's own step still sends a post-game portal on; otherwise it is skipped.
from dw import *
from dw.names import *
from dw.base.freezeland_92 import freezeland
from ...state import root3

@freezeland.on_step(0, when=root3)
def no_barrier():
    if back_dimension_portal == 1:
        tamer.walk(170, -956, wait=False)
        warp(Screen.back_dimension_226, entry=0, then=60)
    dws("return;")                # the barrier's push back must not run
