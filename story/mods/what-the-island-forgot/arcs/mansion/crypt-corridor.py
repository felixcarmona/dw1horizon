# 307, the Grey Lord's Crypt, the niche corridor (§5.4). Its music.
from dw import *

corridor = new_screen(307, map="build/what-the-island-forgot-maps/screens/CRYP01.MAP")
chest_crypt = flag()

@corridor.on_enter
def enter():
    spawn_chest(Item.DefChip, at=(0, -1000), opened=chest_crypt)
    music(10)                     # the mansion basement's
