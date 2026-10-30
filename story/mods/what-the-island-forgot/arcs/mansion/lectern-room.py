# 308, the Grey Lord's Crypt, the lectern room (§3.4, §5.4): Myotismon, who knows the old writing the tamer cannot read,
# brings a book of the library down to the lectern and reads it (fragment M9).
from dw import *
from ...state import root2, memories, m9_library, m11_field, memory_news

room = new_screen(308, map="build/what-the-island-forgot-maps/screens/CRYP02.MAP")
reader = room.npc(Species.Myotismon, at=(601, -2533), range=0, when=root2)

@room.on_enter
def enter():
    music(10)                     # the mansion basement's

@reader.on_talk(when=not m9_library, scene=True)
def reads_the_library():
    face(tamer)
    tamer.face(reader)
    say("You came. I brought one of the books from the library above.", "It is written in the old writing of the city. I can read it, a little.")
    say("\"This house was written by the one below.\"")
    say("\"The Grey Lord was made to forget everything but one name.\"")
    tamer.say("What name?")
    say("It does not say. Only that he kept it to the end, and that it was not his own.")
    m9_library.set()
    memories.add(1)
    memory_news.set()
    if m11_field:
        tamer.say("The one below... Like the man MasterTyrannomon saw go down into the ground?")
        say("Perhaps.")
    say("I shall stay a while. The dead deserve a reader.")

@reader.on_talk
def stays():
    say("Go on, boy. I am in good company here.")
