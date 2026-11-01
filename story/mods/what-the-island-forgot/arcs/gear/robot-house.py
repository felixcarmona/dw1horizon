# 146, the Robot House (§3.6): the tamer comes back with the gear WaruMonzaemon took. If Andromon has already read the
# island's history (the archive "partly repairable"), the tamer remembers that a gear of the old make would complete it:
# give it to the Toys (the game's own scene: Hagurumon comes home, the song, Monzaemon joins) or take it to Andromon
# first: Andromon reads it and the tamer brings it back, and the game's own scene runs then.
from dw import *
from dw.names import *
from dw.base.robot_house import tinmon0
from ...state import gear_for_andromon, m3_archive

gear_offered = flag()

@tinmon0.on_talk(when=island_history_read and recruited(Species.WaruMonzaemon) and not toy_tale_heard and has(Item.Gear)
                 and not gear_for_andromon and not gear_offered)
def whose_gear():
    tamer.say("This gear... It's old. Really old.", "Andromon said the archive in Factorial Town was missing a piece.",
              "A gear of the old make would complete it.")
    gear_offered.set()            # the game's own scene below talks to Tinmon again: this question must not come back
    if ask(yes="It belongs here", no="Keep it for Andromon"):
        return tinmon0.talk()
    say("Oh... You're taking it away? But Hagurumon... Our friend...")
    tamer.say("Sorry. I think the whole island needs to remember something.", "I'll bring it back.")
    gear_for_andromon.set()

@tinmon0.on_talk(when=gear_for_andromon and has(Item.Gear) and not m3_archive)
def gear_kept():
    say("Hagurumon would like to come home... But if it's for everyone, bring it back after.")
