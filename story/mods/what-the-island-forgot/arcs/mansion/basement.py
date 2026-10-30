# 66, the Mansion Basement (§3.4, §5.4): the slab beside the rune circle (maps/chka01-trapdoor.py, step trigger 1). After
# "Let him rest" (R2) the circle is closed and the slab opens on the stairs down to the Grey Lord's Crypt; before that it
# does not move.
from dw import *
from dw.base.mansion_basement import basement
from ...state import root2

@basement.on_step(1, when=root2)
def down_to_the_crypt():
    warp(307, entry=0)

@basement.on_step(1, when=not root2)
def the_slab():
    tamer.say("A stone slab in the floor... It won't budge.")
    tamer.walk(-72, -1598)
