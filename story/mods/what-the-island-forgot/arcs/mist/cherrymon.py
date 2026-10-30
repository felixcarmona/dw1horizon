# 119, Misty Trees, Cherrymon (§3.1d): once the fog is lifted, and once Leomon has read the shrine's second stone (M2),
# Cherrymon hears it from the tamer and remembers what it "must tell" (the end of the legend, fragment M4).
# With the fog kept (fog.py) this waits until the fog is cleared, after Toy Town.
from dw import *
from dw.names import *
from dw.base.misty_trees_119 import cherrymon
from ...state import memories, memory_news, m2_stone, m4_legend

@cherrymon.on_talk(when=misty_trees_fog_lifted and m2_stone and not m4_legend, scene=True)
def the_end_of_the_legend():
    face(tamer)
    tamer.say("Cherrymon, Leomon read us a stone in his ancestors' shrine.", "\"We stood as one at the center, and the center held.\"")
    say("At the center... Ho ho... Ho...")
    wait(1000)
    say("Yes. Yes, that is the part I could not reach. The end of the legend.")
    say("\"When the city is in peril, the city must call.\"", "\"Not fight: call.\"")
    m4_legend.set()
    memories.add(1)
    memory_news.set()
    say("The city calls, and they come. That is how it held, long ago. Ho ho ho...")
