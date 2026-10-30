# 325, the Kennel (design/arc-seam.md §2, story-bible.md §3.8): the hunters' dead-end chamber, with cages of light.
# Its keeper is the named hunter, a DarkLizardmon (Overdell's stats): a scripted battle, no running. Beaten (flag H), it
# runs, and the one Digimon still in a cage, a Gekomon "being erased", remembers itself and goes to the city (its
# origin: it lives in the Works' Scrap Office, district/scrap-office.py).
from dw import *
from dw.text import text
from ...state import hunter_beaten

kennel = new_screen(325, map="build/what-the-island-forgot-maps/screens/SEAM03.MAP")
chest_kennel = flag()
keeper = kennel.npc(Species.DarkLizardmon, at=(0, -500), hp=1500, mp=2500, offense=380, defense=200, speed=120, brain=150,
                    bits=800, range=0, when=not hunter_beaten)
caged = kennel.npc(Species.Gekomon, at=(-600, 300), range=0, when=not recruited(Species.Gekomon))

@keeper.on_talk(scene=True)
def the_named_hunter():
    face(tamer)
    tamer.face(keeper)
    say(text.s034.sec7.u0)
    say("Nobody leaves this place with a name. Not them, not you.")
    if fight(keeper, escape=False) != "won":
        return                    # a lost battle wakes the tamer in Jijimon's house: the hunter waits here still
    say("I am not allowed a single mistake... and now...")
    hunter_beaten.set()
    sound(8, 13)
    wait(1000)
    leave()                       # (walk_away after its battle never ended: the scene hung there, twice)
    warp(325, entry=0)            # the screen again: Gekomon walked out of its cage for the battle (every bystander does)

@caged.on_talk(when=hunter_beaten, scene=True)
def remembers_itself():
    face(tamer)
    say("Orders... Important... Orders...")
    tamer.say("Hey. Hey! You're free now. The hunter's gone.")
    wait(1000)
    say("...Gero? Where... I am Gekomon. I am Gekomon! I play the horn in the swamp!", "I had almost forgotten my own name.")
    send_to_city(line="Gekomon joined the city!", species=Species.Gekomon)

@caged.on_talk
def being_erased():
    say("Orders. Important. Orders. Important...")

@kennel.on_enter
def enter():
    spawn_chest(Item.OffChip, at=(600, 300), opened=chest_kennel)
