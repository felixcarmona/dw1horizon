# 301, the Rift (§5.3): the old canyon floor under the raised plateau, with the human camp. The canyon's music, and the
# camp's board, in a writing only the tamer can read: CAMP 3, the camp the notebook of CAMP 2 was heading for. (The
# board is still blank in the picture: the sign as art is to do.)
from dw import *

rift = new_screen(301, map="build/what-the-island-forgot-maps/screens/RIFT01.MAP")
chest_rift = flag()
board_read = flag()

@rift.on_enter
def enter():
    spawn_chest(Item.Medicine, at=(-500, 300), opened=chest_rift)
    music(6)
    if not board_read:
        the_board()

def the_board():
    tamer.say("A board, nailed to a post... The letters are almost gone.", "\"CAMP 3\". It's human writing. A human camp, down here!")
    board_read.set()
