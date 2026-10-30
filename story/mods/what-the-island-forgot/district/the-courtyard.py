# 358, the Courtyard: the green half of the Works. NiseDrimogemon dug the old well, ModokiBetamon lives by it and
# J-Mojyamon naps on the stones, each beaten first where it lived (the savanna, the forest rivers, the jungle).
from dw import *

courtyard = new_screen(358, map="build/what-the-island-forgot-maps/screens/BARR02.MAP")
nisedrimogemon = courtyard.npc(Species.NiseDrimogemon, at=(-1700, 1000), range=0, when=recruited(Species.NiseDrimogemon))
modokibetamon = courtyard.npc(Species.ModokiBetamon, at=(-2100, 600), range=0, when=recruited(Species.ModokiBetamon))
jmojyamon = courtyard.npc(Species.JMojyamon, at=(-1700, -2100), range=0, when=recruited(Species.JMojyamon))


@nisedrimogemon.on_talk
def talk():
    say("I dug that well with my own drill! ...It is a fake drill. The water is real, though.")


@modokibetamon.on_talk
def talk():
    say("The well is deep and cool. Rivers move too much. A well just sits there, like me.")


@jmojyamon.on_talk
def talk():
    if clock.hour >= 12 and clock.hour < 16:
        say("Zzz... the stones are warm after noon... zzz...")
    else:
        say("The jungle was hot and wet. Here it is only hot. I call that a holiday.")

