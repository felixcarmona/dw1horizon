# The hunters' ambush in the Grey Lord's Mansion's hall (screen 52), after R2 (§3.8): one night only (20:00 to midnight),
# the first time the tamer comes by; no escort. It was in Overdell Cemetery (35), whose seven Digimon leave the hunter
# the last slot: its battle froze there in its animation (tickAnimation never ended), with a DarkLizardmon and with a
# Gururumon alike.
from dw import *
from dw.text import text
from dw.base.grey_lords_mansion_52 import mansion
from ...state import root2, ambush2_fought, hunter_beaten

hunter = mansion.npc(Species.Gururumon, at=(-900, 200), hp=2400, mp=3000, offense=480, defense=260, speed=180, brain=220, bits=900,
                 range=600, autotalk=True, when=root2 and not ambush2_fought and clock.hour >= 20)

@hunter.on_talk(scene=True)
def the_ambush():
    face(tamer)
    tamer.face(hunter)
    partner.face(hunter)
    say(text.s034.sec7.u0)
    say("You broke what was not yours to break. The one below wants you erased.")
    if fight(hunter, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: it waits here still
    ambush2_fought.set()
    say("This is not... the last of us...")
    leave()
