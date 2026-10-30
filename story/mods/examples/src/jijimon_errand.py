# Jijimon's errand, a quest in three stages: bring him two Meat for 1000 bits.
#   python3 tools/dws.py check story/mods/examples/src/jijimon_errand.py --build
from dw import *
from dw.base.jijimons_house import jijimon

class Errand(Quest):
    NONE = auto()       # not asked yet (or you said no)
    ASKED = auto()      # you promised two Meat
    DONE = auto()       # paid

@jijimon.on_talk(when=Errand.NONE)
def asks():
    say("My pantry is empty and my old legs are tired.", "Could you bring me two Meat? I will pay well.")
    if ask(yes="I'll do it", no="Not now"):
        say("Splendid! Two Meat, and you will have 1000 bits.")
        advance(Errand.ASKED)
    else:
        say("Ah well. If you change your mind, I am here.")

@jijimon.on_talk(when=Errand.ASKED)
def waits():
    if has(Item.Meat, 2):
        say("Two fine pieces of Meat! Here are your bits, as promised.")
        take(Item.Meat, 2)
        give(bits=1000)
        advance(Errand.DONE)
    else:
        say("No Meat yet? The Native Forest is full of it, they say.")

@jijimon.on_talk(when=Errand.DONE)
def thanks():
    say("Thank you again for the Meat. My pantry has never been happier.")
