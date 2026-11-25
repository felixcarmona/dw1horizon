# 146, the Robot House (§3.6): the tamer comes back with the gear WaruMonzaemon took. If Andromon has already read the
# island's history (the archive "partly repairable"), the tamer remembers that a gear of the old make would complete it:
# give it to the Toys (the game's own scene: Hagurumon comes home, the song, Monzaemon joins) or take it to Andromon
# first: Andromon reads it and the tamer brings it back, and the game's own scene runs then.
from dw import *
from dw.names import *
from dw.base.robot_house import house, tinmon0
from ...state import gear_for_andromon, m3_archive
from ...state import challenger, challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_MONZAEMON

gear_offered = flag()

@house.on_step(0, when=gear_for_andromon and not m3_archive)
def taking_gear_to_andromon():
    # The original floor greeting walks us back to Tinmon on every attempt to leave.
    # End this tile section while the scan is pending; direct talks still answer.
    dws("return;")

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


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Monzaemon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home, at Jijimon's house (city/jijimons-house-206.py).
monzaemon = house.npc(Species.Monzaemon, at=(-50, -50), bits=300, range=0, still=True, when=challenger == CH_MONZAEMON, alone=challenger == CH_MONZAEMON)



@monzaemon.on_talk
def challenge_monzaemon():
    if challenger != CH_MONZAEMON:
        say(t("challenge.home"))
        leave()
    else:
        if challenge_tried:
            say(t("monzaemon.challenge.retry"))
        else:
            say(t("monzaemon.challenge.intro1"), t("monzaemon.challenge.intro2"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(1)
            if fight(monzaemon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("monzaemon.challenge.won"))
                give(Item.RedRuby)
                give(bits=4000)
                narrator.say(t("monzaemon.challenge.reward"))
                challenger.add(CHALLENGE_BEATEN)
                run(350, -2350)
                leave()
