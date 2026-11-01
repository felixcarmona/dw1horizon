# 162, Factorial Town, the remodelling machine (§3.5): with the factory kept shut its power is the archive's. And Datamon sorts
# the scrap behind the machine into piles only it understands (arcs/residents/README.md; its home: district/scrap-office.py),
# a fight at the town's strength.
from dw import *
from dw.base.factorial_town_162 import guardromon0
from ...state import factory_kept_shut

machine_room = screen(Screen.factorial_town_162)
datamon = machine_room.npc(Species.Datamon, at=(100, -1450), hp=3000, mp=3800, offense=640, defense=340, speed=320, brain=350, bits=1300,
                           range=0, when=not recruited(Species.Datamon))

@guardromon0.on_talk(when=factory_kept_shut)
def no_power():
    say("Remodeling unavailable. All power is assigned to the archive.")


@datamon.on_talk
def talk():
    say("Everything lost ends up in a file. I keep the files.")
    if fight(datamon) == "won":
        say("You are worth a file of your own.")
        send_to_city(line="Datamon joined the city!", species=Species.Datamon)
