# The hunters' ambush in Misty Trees (screen 118), after R3 (§3.8): one night only (20:00 to midnight), the first time
# the tamer comes by. Two Gururumon: a DarkLizardmon and a Gururumon do not fit the screen's heap together.
from dw import *
from dw.text import text
from dw.base.misty_trees_118 import trees
from ...state import root3, ambush3_fought, hunter_beaten

hunter = trees.npc(Species.Gururumon, at=(100, 800), hp=3200, mp=3600, offense=540, defense=300, speed=200, brain=260, bits=1200,
                 range=600, autotalk=True, when=root3 and not ambush3_fought and clock.hour >= 20)
escort = trees.npc(Species.Gururumon, at=(300, 1100), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                 range=0, behaves_like=hunter, when=root3 and not ambush3_fought and not hunter_beaten and clock.hour >= 20)

@hunter.on_talk(scene=True)
def the_ambush():
    face(tamer)
    tamer.face(hunter)
    partner.face(hunter)
    say(text.s096.sec7.u0)
    say("You broke what was not yours to break. The one below wants you erased.")
    if hunter_beaten:
        if fight(hunter, escape=False) != "won":
            return                # a lost battle wakes the tamer in Jijimon's house: they wait here still
    elif fight(hunter, escort, escape=False) != "won":
        return
    ambush3_fought.set()
    say("This is not... the last of us...")
    escort.leave()
    leave()
