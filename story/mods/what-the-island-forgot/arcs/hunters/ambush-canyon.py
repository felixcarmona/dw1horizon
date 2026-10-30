# The hunters' ambush in the Great Canyon (screen 41), after R1 (§3.8): one night only (20:00 to midnight), the first
# time the tamer comes by.
from dw import *
from dw.text import text
from dw.base.great_canyon_bot_area_41 import area
from ...state import root1, ambush1_fought, hunter_beaten

hunter = area.npc(Species.Gururumon, at=(1200, -200), hp=1600, mp=2800, offense=420, defense=220, speed=240, brain=220, bits=600,
                 range=600, autotalk=True, when=root1 and not ambush1_fought and clock.hour >= 20)
escort = area.npc(Species.Gururumon, at=(900, 100), hp=1200, mp=2700, offense=400, defense=190, speed=240, brain=200, bits=400,
                 range=0, behaves_like=hunter, when=root1 and not ambush1_fought and not hunter_beaten and clock.hour >= 20)

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
    ambush1_fought.set()
    say("This is not... the last of us...")
    leave()
