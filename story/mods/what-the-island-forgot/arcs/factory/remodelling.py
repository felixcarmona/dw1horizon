# 162, Factorial Town, the remodelling machine (§3.5): with the factory kept shut its power is the archive's. And Datamon sorts
# the scrap behind the machine into piles only it understands (arcs/residents/README.md; its home: district/scrap-office.py),
# a fight at the town's strength.
from dw import *
from dw.base.factorial_town_162 import guardromon0
from dw.text import text
from ...state import factory_kept_shut

machine_room = screen(Screen.factorial_town_162)
datamon = machine_room.npc(Species.Datamon, at=(100, -1450), hp=3000, mp=3800, offense=640, defense=340, speed=320, brain=350, bits=1300,
                           range=0, still=True, when=not recruited(Species.Datamon))

@guardromon0.on_talk(when=factory_kept_shut)
def no_power():
    say("Remodeling unavailable. All power is assigned to the archive.")


@datamon.on_talk
def talk():
    say("Everything lost ends up in a file. I keep the files.")
    if fight(datamon) == "won":
        say("You are worth a file of your own.")
        send_to_city(line="Datamon joined the city!", species=Species.Datamon)


# More remodelling (Discord, 2026-11): Guardromon also reworks the species that have a same-level sibling, always one step
# sideways (never up a stage), for the Mamemon's own fee and odds: 1 in 10 the special form, 5 in 10 the usual one, the rest
# fails. Species past 255 cannot be a partner (pstats holds one byte), so only ids up to 255 appear. The conversation is the
# base game's, with the species test moved into the result.
t5 = text.s156.sec5


@guardromon0.on_talk(when=not factory_kept_shut)
def remodel():
    raw.entity_walk_to_entity(partner, 1, tamer)
    tamer.arrived()
    say(t5.u0)
    if partner.species == Species.Mamemon or partner.species == Species.Numemon or partner.species == Species.Geremon \
            or partner.species == Species.MegaSeadramon or partner.species == Species.WaruSeadramon \
            or partner.species == Species.MetalGreymonVirus or partner.species == Species.MetalGreymonVaccine:
        match choose(a=t5.m0.o0, b=t5.m0.o1):
            case "a":
                if bits < 2000:
                    say(t5.u2)
                else:
                    take(bits=2000)
                    say(t5.u3)
                    roll = random.roll(10)
                    if roll <= 0:
                        say(t5.u4)
                        hide_hud()
                        if partner.species == Species.Mamemon:
                            engine.arg.set(Species.Giromon)
                        elif partner.species == Species.Numemon or partner.species == Species.Geremon:
                            engine.arg.set(Species.ShellNumemon)
                        elif partner.species == Species.MegaSeadramon:
                            engine.arg.set(Species.WaruSeadramon)
                        elif partner.species == Species.WaruSeadramon:
                            engine.arg.set(Species.MegaSeadramon)
                        elif partner.species == Species.MetalGreymonVirus:
                            engine.arg.set(Species.MetalGreymonVaccine)
                        else:
                            engine.arg.set(Species.MetalGreymonVirus)
                        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                        wait(28500)
                        tamer.say("Whoa, it changed form!")
                    elif roll <= 5:
                        say(t5.u6)
                        hide_hud()
                        if partner.species == Species.Mamemon:
                            engine.arg.set(Species.MetalMamemon)
                        elif partner.species == Species.Numemon:
                            engine.arg.set(Species.Geremon)
                        elif partner.species == Species.Geremon:
                            engine.arg.set(Species.ShellNumemon)
                        elif partner.species == Species.MegaSeadramon:
                            engine.arg.set(Species.WaruSeadramon)
                        elif partner.species == Species.WaruSeadramon:
                            engine.arg.set(Species.MegaSeadramon)
                        elif partner.species == Species.MetalGreymonVirus:
                            engine.arg.set(Species.MetalGreymonVaccine)
                        else:
                            engine.arg.set(Species.MetalGreymonVirus)
                        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                        wait(28500)
                        tamer.say("Whoa, it changed form!")
                    else:
                        say(t5.u8)
                        tamer.say(t5.u9)
                        say(t5.u10)
    else:
        say(t5.u1)
