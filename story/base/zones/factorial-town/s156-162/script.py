# The Python view of script 156 of DG.SCN: screen 162 Factorial Town.
# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the
# game's words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.
from dw import *
from dw.text import text

town = screen(Screen.factorial_town_162)
guardromon0 = town.npc(Species.Guardromon, slot=0)
guardromon1 = town.npc(Species.Guardromon, slot=1)
guardromon2 = town.npc(Species.Guardromon, slot=2)
t5 = text.s156.sec5
t6 = text.s156.sec6
t7 = text.s156.sec7

@town.on_enter
def enter():    # section 254
    spawn_chest(Item.DefChip, at=(82, -1000), opened=trigger(714), facing=3072)
    spawn_chest(Item.AutoPilot, at=(32, -1535), opened=trigger(715), facing=3072)
    spawn_chest(Item.BrainChip, at=(1889, -2267), opened=trigger(716), facing=1024)

@guardromon0.on_talk
def talk():    # section 5
    raw.entity_walk_to_entity(partner, 1, tamer)
    tamer.arrived()
    say(t5.u0)
    if partner.species != Species.Mamemon:
        say(t5.u1)
        return
    match choose(a=t5.m0.o0, b=t5.m0.o1):
        case "a":
            if bits < 2000:
                say(t5.u2)
                return
            take(bits=2000)
            say(t5.u3)
            roll = random.roll(10)
            if roll <= 0:
                say(t5.u4)
                hide_hud()
                engine.arg.set(41)
                raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                wait(28500)
                tamer.say(t5.u5)
                return
            if roll <= 5:
                say(t5.u6)
                hide_hud()
                engine.arg.set(27)
                raw.call_digimon_routine(DigimonRoutine.forced_evolution)
                wait(28500)
                tamer.say(t5.u7)
                return
            say(t5.u8)
            tamer.say(t5.u9)
            say(t5.u10)
        case _:
            return

@guardromon1.on_talk
def talk():    # section 6
    recruitable(guardromon1, line=t6.u0)

@guardromon2.on_talk
def talk():    # section 7
    recruitable(guardromon2, line=t7.u0)
    return

# the section table, in the order of the original header
sections(254, 5, 6, 7)
