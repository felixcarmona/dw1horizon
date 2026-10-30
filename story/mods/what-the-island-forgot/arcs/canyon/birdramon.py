# R1's price (§3.2): with the Motor broken the high ground sinks and Birdramon's nest falls in. Birdramon comes down to the
# Great Canyon Bridge (39) looking for whoever did it, fights the tamer, and once beaten leaves the island:
# no Birdramon in the city, no Birdra Transport, never a rescuer at the summit.
from dw import *
from dw.base.great_canyon_bridge import bridge
from ...state import root1, birdramon_gone

birdramon = bridge.npc(Species.Birdramon, at=(-1055, -3570), range=0, autotalk=True,
                       when=root1 and not birdramon_gone and not recruited(Species.Birdramon))

@birdramon.on_talk(scene=True)
def the_culprit():
    face(tamer)
    tamer.face(birdramon)
    partner.face(birdramon)
    say("You. The ground under my nest went down in one night.", "Something under the canyon stopped. You were there.")
    tamer.say("The Motor... It was pushing the whole canyon up! It wasn't right!")
    say("Maybe. My house is gone all the same.")
    if fight(birdramon, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: Birdramon waits here still
    say("Heh... Not bad, kid.")
    say("I carry anything, kid. Not for the one who dropped my house.")
    birdramon_gone.set()
    sound(8, 13)                  # wings (the nest scene's): it flies off (walk_away after its battle hung the scene)
    wait(1000)
    leave()
    narrator.say("Birdramon left the island.")
