# Drill Tunnel 24: Digmon digs alone. It builds the Works, so its fight opens the gate in the hedge (arcs/works/gate.py).
# Stand beside the west wall so the cart route stays clear.
# Its home is the Stone Yard (district/stone-yard.py). The stats match the tunnel's wild fights.
from dw import *
from ...state import new_challenger, new_challenge_tried, CHALLENGE_ARMED, CHALLENGE_BEATEN, CH_DIGMON

tunnel = screen(Screen.drill_tunnel_24)
digmon = tunnel.npc(Species.Digmon, at=(-2250, 1100), hp=1000, mp=1800, offense=250, defense=130, speed=80, brain=100, bits=300,
                    range=0, still=True, when=not recruited(Species.Digmon) or new_challenger == CH_DIGMON, alone=new_challenger == CH_DIGMON)


# Resident challenges (content/tables/resident-challenges.json): once the game is beaten, the day Digmon is the challenger
# and has not been beaten yet it waits here, stronger; any other day it is home.

def challenge():
    if new_challenger != CH_DIGMON:
        say(t("challenge.home"))
        leave()
    else:
        if new_challenge_tried:
            say(t("digmon.challenge.retry"))
        else:
            say(t("digmon.challenge.intro1"), t("digmon.challenge.intro2"))
        say(t("challenge.noitems"))
        if ask(yes=t("challenge.yes"), no=t("challenge.no")):
            new_challenge_tried.set()
            pstat(CHALLENGE_ARMED).set(2)
            if fight(digmon, escape=False) == "won":       # a lost one wakes the tamer at Jijimon's: it waits here all day
                say(t("digmon.challenge.won"))
                give(Item.SteelDrill)
                give(bits=2500)
                narrator.say(t("digmon.challenge.reward"))
                new_challenger.add(CHALLENGE_BEATEN)
                run(-1950, 150)
                leave()


@digmon.on_talk
def talk():
    if recruited(Species.Digmon):
        challenge()
    else:
        say("Every tunnel on this island is mine, and nobody ever comes back to thank me.")
        say("Prove your partner is worth a building.")
        if fight(digmon, escape=False) == "won":
            say("I could build a whole district for someone like that.")
            run(-1950, 1850)
            send_to_city(line="Digmon joined the city!", species=Species.Digmon, camera=False)
