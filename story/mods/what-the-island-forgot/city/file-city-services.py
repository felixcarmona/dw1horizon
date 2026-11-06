# File City's top map (script 162): two residents who had nothing to do. Sukamon, at night, sweeps the island's poop for
# 1000 bits; Andromon, on the days it comes by, remodels a Mamemon as the Guardromon of Factorial Town do, in their words.
from dw import *
from dw.names import *
from dw.text import text
from dw.base.file_city_168 import andromon, sukamon

t5 = text.s156.sec5

@sukamon.on_talk(when=recruited(Species.Sukamon))
def sweep():
    say("Poop, poop, everywhere! For 1000 Bits I'll clean up the whole island.")
    if not ask(yes="Clean it up", no="No thanks"):
        return
    if bits < 1000:
        say(t5.u2)
        return
    take(bits=1000)
    raw.call_digimon_routine(DigimonRoutine.clear_poop)
    say("All gone! Not a single pile left on the island.")

@andromon.on_talk(when=recruited(Species.Andromon))
def remodel():
    if partner.species != Species.Mamemon:
        say(text.s162.sec7.u0)
        return
    say(t5.u0)
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
