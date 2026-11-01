# 312, the Infinity Engine room (§3.9, §5.9): the program Analogman compiles inside the mountain, an empty door at the
# back. Analogman's third notebook lies here, read on every path (it is not a memory fragment). With R2 Devimon waits here
# for the fight it skipped on 247.
from dw import *
from dw.text import text
from dw.names import *
from ...state import notebook3, m5_notebook, m6_notebook, root2, devimon_fought

engine_room = new_screen(312, map="build/what-the-island-forgot-maps/screens/INFE01.MAP")
devimon = engine_room.npc(Species.Devimon130, at=(1000, 800), range=0, when=root2 and mt_infinity_devimon_beaten and not devimon_fought)
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
