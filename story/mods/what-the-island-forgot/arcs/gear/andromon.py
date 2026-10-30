# 157, Factorial Town, Andromon (§3.6): with the old gear the archive is complete, and Andromon reads the whole war aloud
# (fragment M3, complete: it counts twice).
from dw import *
from dw.base.factorial_town_157 import andromon
from ...state import gear_for_andromon, m3_archive, m3_stations, memories, memory_news

@andromon.on_talk(when=gear_for_andromon and has(Item.Gear) and not m3_archive)
def the_whole_war():
    say("That gear. It is of the old make. Permission to install it?")
    take(Item.Gear)
    sound(8, 4)
    wait(1500)
    say("The archive is complete. Reading.")
    say("A hundred years ago, humans came to this island.", "They fought the Digimon for ten years.",
        "The Digimon stood together at the center of the island, and the humans were defeated.")
    say("The record of the humans' leader ends there.", "The leader did not vanish. The record of his death is missing.")
    say("Ten years later, the island had grown to almost twice its size.", "The new land is not in the archive.",
        "It was written from somewhere else.")
    tamer.say("Written... by him. From inside the island.")
    say("That is consistent with the data.")
    m3_archive.set()
    if m3_stations:
        memories.add(1)           # M3 complete counts two in all; the stations (M3+) were one
    else:
        memories.add(2)
    memory_news.set()
