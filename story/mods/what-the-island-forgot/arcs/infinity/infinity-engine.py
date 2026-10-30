# 312, the Infinity Engine room (§3.9, §5.9): the program Analogman compiles inside the mountain, an empty door at the
# back. Analogman's third notebook lies here, read on every path (it is not a memory fragment).
from dw import *
from ...state import notebook3, m5_notebook, m6_notebook

engine_room = new_screen(312, map="build/what-the-island-forgot-maps/screens/INFE01.MAP")

@engine_room.on_enter
def the_third_notebook():
    music(27)                     # Mt. Infinity's
    if not notebook3:
        tamer.say("Machines everywhere... and a door at the back that doesn't lead anywhere.")
        if m5_notebook or m6_notebook:
            tamer.say("Another notebook. The same handwriting.")
        else:
            tamer.say("A notebook... It's in human writing!")
        tamer.say("\"The door opens from the other side. I have no other side.\"", "\"Then I will make the island my other side.\"")
        notebook3.set()
        tamer.say("He wants to get out. Through a door he's making himself...")
