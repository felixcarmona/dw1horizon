# 313, the Infinity Engine room with the three roots broken (§3.9): the lights are dead and the program spits errors.
# The third notebook is read here too.
from dw import *
from ...state import notebook3, m5_notebook, m6_notebook

dark_room = new_screen(313, map="build/what-the-island-forgot-maps/screens/INFE02.MAP")

@dark_room.on_enter
def the_third_notebook():
    music(27)                     # Mt. Infinity's
    if not notebook3:
        tamer.say("It's all dark... Those red lights keep blinking. Something's broken.")
        if m5_notebook or m6_notebook:
            tamer.say("A notebook, in the same handwriting.")
        else:
            tamer.say("A notebook... It's in human writing!")
        tamer.say("\"The door opens from the other side. I have no other side.\"", "\"Then I will make the island my other side.\"")
        notebook3.set()
        tamer.say("The canyon, the mansion, the ice... They were all feeding this.", "And now there's nothing left to feed it.")
