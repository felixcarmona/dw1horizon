# Tokomon's sparring match: a scripted battle with a reward, once.
#   python3 tools/dws.py check story/mods/examples/src/tokomon_sparring.py --build
from dw import *
from dw.base.jijimons_house import tokomon

sparring_won = flag()

@tokomon.on_talk(when=sparring_won)
def proud():
    say("You beat me fair and square. I'm still training!")

@tokomon.on_talk(when=not sparring_won)
def challenge():
    say("Hey! Want to spar? I've been practicing my bubbles!")
    if ask(yes="Let's go", no="Maybe later"):
        say("Here I come!")
        if fight(tokomon) == "won":
            say("Wow, you're strong! Take this, you earned it.")
            give(bits=500)
            sparring_won.set()
        else:
            say("Hehe, I won! Come back when you're ready.")
    else:
        say("Okay, I'll keep practicing then.")
