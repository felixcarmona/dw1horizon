# 119, Misty Trees, Cherrymon's first meeting (§3.1d): the game's own tale by its keys, then the one-time question:
# clear the fog (the game's own end: the forest and Toy Town in sight, and the hunters' patrols) or keep the forest
# hidden. Once Toy Town is done (the Toys' song, or the gear taken to Andromon), a kept fog can be cleared. Setting
# cherrymon_met here makes the game's own scene return at once after this one.
from dw import *
from dw.text import text
from dw.names import *
from dw.base.misty_trees_119 import trees, cherrymon
from ...state import fog_kept, gear_for_andromon

t51 = text.s115.sec51

@trees.on_step(0, when=not cherrymon_met)
def the_tale():
    cherrymon_met.set()
    tamer.run(-1606, 166, camera=True, wait=False)
    partner.run(-1407, 465)
    tamer.arrived()
    tamer.face(cherrymon)
    cherrymon.face(tamer)
    partner.face(cherrymon)
    sound(8, 18)
    cherrymon.say(t51.u0)
    tamer.play(20)
    wait(750)
    if recruited(Species.Otamamon):
        tamer.say(t51.u1)
    else:
        tamer.say(t51.u2)
    tamer.play(anim.idle)
    cherrymon.say(t51.u3)
    if recruited(Species.Otamamon):
        tamer.say(t51.u4)
    else:
        tamer.say(t51.u5)
    sound(8, 18)
    cherrymon.say(t51.u6)
    tamer.play(19)
    wait(750)
    tamer.say(t51.u7)
    tamer.play(anim.idle)
    cherrymon.say(t51.u8)
    tamer.say(t51.u9)
    cherrymon.say(t51.u10)
    sound(8, 18)
    cherrymon.say(t51.u11)
    sound(8, 18)
    raw.show_textbox(t51.u12)
    sound(8, 18)
    raw.show_textbox(t51.u13)
    cherrymon.say("The fog has hidden this forest a long time.", "The hunters cannot find what they cannot see.",
                  "Shall I clear it, young man, or keep it?")
    if ask(yes="Clear it", no="Keep it"):
        clear_the_fog()
    else:
        fog_kept.set()
        cherrymon.say("Ho ho. Then the forest stays hidden. The charm you carry will lead you through.",
                      "But while I hold the fog, I have no strength left for remembering.")
        cherrymon.play(29)
        wait(3000)

def clear_the_fog():
    misty_trees_fog_lifted.set()
    sound(8, 18)
    cherrymon.say(t51.u14)
    call(Routine.remove_fog)
    cherrymon.say(t51.u15)
    sound(8, 18)
    raw.show_textbox(t51.u16)
    cherrymon.play(29)
    wait(3000)

@cherrymon.on_talk(when=fog_kept and not misty_trees_fog_lifted and toy_tale_heard, scene=True)
def after_toy_town():
    lift_it_now()

@cherrymon.on_talk(when=fog_kept and not misty_trees_fog_lifted and gear_for_andromon, scene=True)
def after_the_gear():
    lift_it_now()

def lift_it_now():
    face(tamer)
    say("Ho ho. The toys are safe again, I hear. Shall I let the fog go now?")
    if ask(yes="Clear it", no="Not yet"):
        fog_kept.clear()
        clear_the_fog()
