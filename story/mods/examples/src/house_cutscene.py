# A short cutscene the first time you enter Jijimon's house, and a line that depends on the clock.
#   python3 tools/dws.py check story/mods/examples/src/house_cutscene.py --build
from dw import *
from dw.base.jijimons_house import house, jijimon, tokomon

intro_seen = flag()

@house.on_enter(when=not intro_seen)
def intro():
    camera.on(tokomon, speed=12)
    camera.arrived()
    tokomon.face(jijimon)
    wait(1000)
    narrator.say("Tokomon yawns and stretches. Another peaceful day is starting in the house.")
    camera.on(tamer)
    camera.arrived()
    intro_seen.set()
    give(bits=100)
    sound.jingle()

@tokomon.on_talk(when=intro_seen)
def greets():
    if clock.hour >= 18 or clock.hour < 5:
        say("Puyo... it is late. The house is quiet and warm.")
    else:
        say("Puyo puyo! I was the first to see you come in.")
