# 309, the Drowned Shore (§3.3, §5.8): the island's old coast under the cliffs of Freezeland, left dry when the island
# grew, with the wreck of a human ship. Only Whamon brings the tamer here (from the city's dock, city-dock.py) and takes
# him back. The first time, a wet notebook in the wreck: one line can still be read (fragment M12).
from dw import *
from ...state import memories, m12_shore, memory_news

shore = new_screen(309, map="build/what-the-island-forgot-maps/screens/SHOR01.MAP")
chest_shore = flag()
whamon = shore.npc(Species.Whamon, at=(750, -650), range=0, autotalk=False)

@shore.on_enter
def the_wreck():
    # West of the narrow strip by the water: opened from its east side, it leaves the way along the beach free.
    spawn_chest(Item.SupRecovery, at=(-1400, -800), opened=chest_shore, facing=3072)
    music(15)                     # Freezeland's
    if not m12_shore:
        tamer.say("Whoa... A ship! A real ship, like from my world. Stuck in the rocks.")
        tamer.walk(250, -400, camera=True)
        tamer.turn(0)
        tamer.say("There's a notebook in the planks. It's soaked... Almost all the ink's run.", "Only one line is left.")
        tamer.say("\"...the children were not supposed to come.\"")
        m12_shore.set()
        memories.add(1)
        memory_news.set()
        tamer.say("Children? There were kids on this ship?")
        camera.on(tamer, speed=10)
        camera.arrived()

@whamon.on_talk
def ride_back():
    say("This was the shore, long ago. The sea pulled back when the island grew. I felt it go.")
    if ask(yes="Let's go back", no="Not yet"):
        say("Then climb onto my back.")
        warp(Screen.secret_beach_cave_142, entry=2, then=61)
