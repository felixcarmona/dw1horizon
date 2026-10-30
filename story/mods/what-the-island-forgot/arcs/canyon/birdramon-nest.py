# 129, Birdramon's nest at the top of the Great Canyon: with the Motor broken (R1) the rock under it has sunk and the
# nest has fallen in; Birdramon is gone (birdramon.py). The canyon's elevators arrive here with section 52 (the
# elevator's sound): with R1 the tamer goes on at once to the fallen nest, screen 366 (maps/nest-fallen.py: our picture
# over the player's GCAN10, the same elevator and arrival). The step on the nest, where the game's scene would recruit
# Birdramon, turns the tamer back on 366 too.
from dw import *
from dw.base.great_canyon_129 import canyon as nest
from ...state import root1

@nest.section(52, when=root1 and not recruited(Species.Birdramon))
def fallen_in():
    warp(366, entry=0)
