# 358, the Courtyard: NiseDrimogemon dug the old well and J-Mojyamon naps on the stones.
# Both were beaten first where they lived, in the savanna and jungle.
from dw import *

courtyard = new_screen(358, map="build/what-the-island-forgot-maps/screens/BARR02.MAP")
nisedrimogemon = courtyard.npc(Species.NiseDrimogemon, at=(-1700, 1000), range=0, when=recruited(Species.NiseDrimogemon))
jmojyamon = courtyard.npc(Species.JMojyamon, at=(-1700, -2100), range=0, when=recruited(Species.JMojyamon))


@nisedrimogemon.on_talk
def talk():
    say("I dug that well with my own drill! ...It is a fake drill. The water is real, though.")


@jmojyamon.on_talk
def talk():
    if clock.hour >= 12 and clock.hour < 16:
        say("Zzz... the stones are warm after noon... zzz...")
    else:
        say("The jungle was hot and wet. Here it is only hot. I call that a holiday.")

