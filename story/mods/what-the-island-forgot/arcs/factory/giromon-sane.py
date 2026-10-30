# 160, Factorial Town, the computer room (§3.5): with the Grey Lord at rest (R2) Devimon lost its strings early, and
# nobody pulls Giromon's either: there is no rampage and no battle. Giromon meets the tamer in its right mind and stops
# the machine itself. Setting factory_giromon_beaten keeps the rest of the game's chain as it is (the waste, Andromon,
# the sewer, the reopening); the game's own scene returns at once.
from dw import *
from dw.names import *
from dw.base.factorial_town_160 import town, giromon
from ...state import root2

@town.on_step(0, when=root2 and not factory_giromon_beaten)
def in_its_right_mind():
    tamer.face(giromon)
    partner.face(giromon)
    giromon.face(tamer)
    giromon.say("Bzzt! I've been waitin' for ya!")
    tamer.say("Huh? You're... not going crazy?")
    giromon.say("Somethin' was buzzin' in my head for weeks. Break this, break that.", "Then one day... click. Gone. Heh-heh-hee!")
    giromon.say("But this computer's been leakin' waste all that time. Go tell Andromon to shut it off, bzzt!")
    tamer.say("Got it! I'll tell Andromon so he can stop the waste.")
    factory_giromon_beaten.set()
    camera.on(tamer, speed=10)
    camera.arrived()
