# 304, the second chamber of Leomon's ancestors' shrine (§3.1b, §5.6): the mural and a second stone in the old writing,
# which only Leomon can read. Once Leomon has joined the city it answers the call ("Whenever you are in trouble, call
# me") and waits here; it reads the stone aloud (fragment M2), then goes back to its patrols.
from dw import *
from ...state import memories, m2_stone, memory_news

chamber = new_screen(304, map="build/what-the-island-forgot-maps/screens/SHRN01.MAP")
leomon = chamber.npc(Species.Leomon, at=(350, 250), range=0, when=recruited(Species.Leomon) and not m2_stone)

@chamber.on_enter
def enter():
    music(4)                     # Leomon's shrine's

@leomon.on_talk(scene=True)
def reads_the_stone():
    face(tamer)
    tamer.face(leomon)
    say("You called, and I came. So this is what lay beyond my ancestors' tablet.")
    tamer.say("Look at the wall. Every kind of Digimon, in a ring around a mountain...",
              "And outside the ring, those little ones. They look like... people.")
    say("And the stone is in the old writing. Let me see...")
    walk(150, 650)
    turn(0)
    wait(1000)
    say("\"They came from beyond. We stood as one at the center, and the center held.\"",
        "\"One of them would not raise a hand against us.\"")
    m2_stone.set()
    memories.add(1)
    memory_news.set()
    face(tamer)
    tamer.say("One of the people didn't fight? Then not all of them were bad.")
    say("It seems my ancestors remembered more than the island does now.", "I will keep watch on the savanna. Call me again if you need me.")
    walk_away(1450, -250, looks=2)
    leave()
