# Drill Tunnel 24: Digmon digs alone. It builds the Works, so its fight opens the gate in the hedge (arcs/works/gate.py).
# Its home is the Stone Yard (district/stone-yard.py). The stats match the tunnel's wild fights.
from dw import *

tunnel = screen(Screen.drill_tunnel_24)
digmon = tunnel.npc(Species.Digmon, at=(-1300, 1800), hp=1000, mp=1800, offense=250, defense=130, speed=80, brain=100, bits=300,
                    range=0, when=not recruited(Species.Digmon))


@digmon.on_talk
def talk():
    say("Every tunnel on this island is mine, and nobody ever comes back to thank me.")
    say("Prove your partner is worth a building.")
    if fight(digmon) == "won":
        say("I could build a whole district for someone like that.")
        send_to_city(line="Digmon joined the city!", species=Species.Digmon)
