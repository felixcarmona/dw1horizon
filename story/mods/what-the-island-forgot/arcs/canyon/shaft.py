# 302, the Shaft (§5.1): the bottom of the Fortress elevator. The canyon's music.
from dw import *

shaft = new_screen(302, map="build/what-the-island-forgot-maps/screens/SHFT01.MAP")

@shaft.on_enter
def enter():
    music(6)
