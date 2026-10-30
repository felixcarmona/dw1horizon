# A Digimon the map never had: a strong Garurumon guards the Native Forest entrance, in the slot of the ModokiBetamon
# there (slot 0), with its own stats. It challenges you; you get a reward the first time you win. Garurumon's model is
# big: the other two ModokiBetamon (slots 1 and 4) become RedVegiemon, so the screen's models still fit in the heap.
# Each is taken over (the mod owns its talk): the base's talk would fight it and recruit a ModokiBetamon, so they say
# the forest RedVegiemon's own line (slot 2's) and recruit a RedVegiemon.
#   python3 tools/dws.py check story/mods/examples/src/forest_garurumon.py --build
from dw import *
from dw.text import text
from dw.base.native_forest_0 import modokibetamon0, modokibetamon1, modokibetamon4

garurumon = take_over(modokibetamon0, species=Species.Garurumon, at=(-2309, 2500),
                      hp=1500, mp=900, offense=200, defense=150, speed=120, brain=150, bits=2000)
vegie1 = take_over(modokibetamon1, species=Species.RedVegiemon)
vegie4 = take_over(modokibetamon4, species=Species.RedVegiemon)
beaten = flag()

@garurumon.on_talk(when=beaten)
def respects():
    say("You again. The forest is yours to cross, Tamer.")

@garurumon.on_talk
def guards():
    say("None shall pass this forest without proving their strength!")
    if fight(garurumon) == "won":
        say("Impressive... take these bits, you have earned them.")
        give(bits=2000)
        beaten.set()

@vegie1.on_talk
def vegie1_talk():
    recruitable(vegie1, line=text.s001.sec7.u0)

@vegie4.on_talk
def vegie4_talk():
    recruitable(vegie4, line=text.s001.sec7.u0)
