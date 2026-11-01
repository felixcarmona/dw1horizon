# R1's price (§3.2): with the Motor broken the high ground sinks and Birdramon's nest falls in. Birdramon comes down to the
# Great Canyon Bridge (39) looking for whoever did it. After the fight it joins the city, still angry.
# Keep the original recruitment reward and city arrival (s124 section 51), including the prosperity-50 boundary.
from dw import *
from dw.base.great_canyon_bridge import bridge
from ...state import root1

birdramon = bridge.npc(Species.Birdramon, at=(-1055, -3570), range=0, autotalk=True,
                       when=root1 and not recruited(Species.Birdramon))

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
    say("I'm still angry. But I'll carry you. I'll work in the city.")
    sound(8, 13)                  # wings (the nest scene's): it flies off (walk_away after its battle hung the scene)
    wait(1000)
    leave()
    recruit(Species.Birdramon, prosperity=2)  # the extended pass supplies the usual join announcement
    # Birdramon is now recruited, so only the six Birdra Transport layouts of s124:51 can apply.
    if not recruited(Species.Angemon) and not recruited(Species.Monzaemon) and engine.prosperity < 50:
        if recruited(Species.Vegiemon):
            warp(Screen.file_city_173, entry=0)
        if recruited(Species.Palmon):
            warp(Screen.file_city_172, entry=0)
        warp(Screen.file_city_171, entry=0)
    if recruited(Species.Vegiemon):
        warp(Screen.file_city_179, entry=0)
    if recruited(Species.Palmon):
        warp(Screen.file_city_178, entry=0)
    warp(Screen.file_city_177, entry=0)
