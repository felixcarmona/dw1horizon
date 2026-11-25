# 359, the Guard House: the Works' watch post. Knightmon, who guarded a door to nothing on Mt. Infinity, has a wall to guard now.
from dw import *

guard_house = new_screen(359, map="build/what-the-island-forgot-maps/screens/BARR03.MAP")
knightmon = guard_house.npc(Species.Knightmon, at=(-500, -400), range=0, when=recruited(Species.Knightmon))


@knightmon.on_talk
def talk():
    if clock.hour >= 20 or clock.hour < 5:
        say("Night watch. The map on the wall is the whole island, every road you have walked.")
    else:
        say("My oath outlived my door. This post watches the stairs.", "Nobody comes up that I do not see.")
