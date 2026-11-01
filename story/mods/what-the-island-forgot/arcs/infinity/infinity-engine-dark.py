# 313, the Infinity Engine room with the three roots broken (§3.9): the lights are dead and the program spits errors.
# The third notebook is read here too, and Devimon waits here as in the lit room (infinity-engine.py).
from dw import *
from dw.text import text
from dw.names import *
from ...state import notebook3, m5_notebook, m6_notebook, root2, devimon_fought

dark_room = new_screen(313, map="build/what-the-island-forgot-maps/screens/INFE02.MAP")
devimon = dark_room.npc(Species.Devimon130, at=(1000, 800), range=0, when=root2 and mt_infinity_devimon_beaten and not devimon_fought)
t53 = text.s194.sec53

@devimon.on_talk(scene=True)
def the_debt_is_paid():
    face(tamer)
    tamer.face(devimon)
    say("Heh heh heh... The debt's paid. Nothing stops us now.")
    if ask(yes="Fight", no="Not now"):
        say(t53.u2)
        if fight(devimon, escape=False) != "won":
            return                # a lost battle wakes the tamer in Jijimon's house: Devimon waits here still
        say(t53.u3)
        devimon_fought.set()
        leave()

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
