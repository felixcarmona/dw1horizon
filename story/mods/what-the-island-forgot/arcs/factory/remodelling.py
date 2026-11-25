# 162, Factorial Town, the remodelling machine (§3.5): with the factory kept shut its power is the archive's. And Datamon sorts
# the scrap behind the machine into piles only it understands (arcs/residents/README.md; its home: district/scrap-office.py),
# a fight at the town's strength.
from dw import *
from dw.base.factorial_town_162 import guardromon0
from dw.text import text
from ...state import factory_kept_shut
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_DATAMON

machine_room = screen(Screen.factorial_town_162)
datamon = machine_room.npc(Species.Datamon, at=(100, -1450), hp=4000, mp=4200, offense=700, defense=370, speed=320, brain=350, bits=1300,
                           range=0, still=True, when=not recruited(Species.Datamon) or new_challenger == CH_DATAMON, alone=new_challenger == CH_DATAMON)

@guardromon0.on_talk(when=factory_kept_shut)
def no_power():
    say("Remodeling unavailable. All power is assigned to the archive.")


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Datamon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.

def challenge():
    if new_challenger != CH_DATAMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("datamon.challenge.retry"))
        else:
            say(t("datamon.challenge.intro1"), t("datamon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(datamon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("datamon.challenge.won"))
                give(Item.CyberPart)
                give(bits=4000)
                narrator.say(t("datamon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(3150, -850)
                leave()


@datamon.on_talk
def talk():
    if recruited(Species.Datamon):
        challenge()
    else:
        say("Everything lost ends up in a file. I keep the files.")
        if fight(datamon, escape=False) == "won":
            say("You are worth a file of your own.")
            run(-50, -2650)
            send_to_city(line="Datamon joined the city!", species=Species.Datamon, camera=False)


# More remodelling (Discord, 2026-11): Guardromon also reworks the species that have a same-level sibling, always one step
# sideways (never up a stage), for the Mamemon's own fee and odds: 1 in 10 the special form, 5 in 10 the usual one, the rest
# fails. Species past 255 cannot be a partner (pstats holds one byte) and the original engine tests only its own 180 species as the
# partner, so only those are remodelled; the results may be any id up to 255. The conversation is the
# base game's, with the species test moved into the result.
t5 = text.s156.sec5


@guardromon0.on_talk(when=not factory_kept_shut)
def remodel():
    raw.entity_walk_to_entity(partner, 1, tamer)
    tamer.arrived()
    say(t5.u0)
    if partner.species == Species.Mamemon or partner.species == Species.Numemon or partner.species == Species.Geremon \
            or partner.species == Species.MegaSeadramon or partner.species == Species.WaruSeadramon \
            or partner.species == Species.MetalGreymonVirus:
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
                            engine.arg.set(41)
                        elif partner.species == Species.Numemon or partner.species == Species.Geremon:
                            engine.arg.set(231)
                        elif partner.species == Species.MegaSeadramon:
                            engine.arg.set(112)
                        elif partner.species == Species.WaruSeadramon:
                            engine.arg.set(61)
                        else:
                            engine.arg.set(224)
                        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                        wait(28500)
                        tamer.say("Whoa, it changed form!")
                    elif roll <= 5:
                        say(t5.u6)
                        hide_hud()
                        if partner.species == Species.Mamemon:
                            engine.arg.set(27)
                        elif partner.species == Species.Numemon:
                            engine.arg.set(87)
                        elif partner.species == Species.Geremon:
                            engine.arg.set(231)
                        elif partner.species == Species.MegaSeadramon:
                            engine.arg.set(112)
                        elif partner.species == Species.WaruSeadramon:
                            engine.arg.set(61)
                        else:
                            engine.arg.set(224)
                        raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                        wait(28500)
                        tamer.say("Whoa, it changed form!")
                    else:
                        say(t5.u8)
                        tamer.say(t5.u9)
                        say(t5.u10)
    else:
        say(t5.u1)
