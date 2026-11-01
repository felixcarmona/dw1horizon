# Gear Savanna 78: Kiwimon will not move until somebody feeds it. A Meat, consumed. No fight. It cooks at the Restaurant
# (city/restaurant-214.py, city/restaurant-215.py).
from dw import *

savanna = screen(Screen.gear_savanna_78)
kiwimon = savanna.npc(Species.Kiwimon, at=(-750, 1750), range=0, when=not recruited(Species.Kiwimon))


@kiwimon.on_talk
def talk():
    say("I'm not moving. I'm too hungry to move. Is that meat I smell?")
    if has(Item.Meat):
        if ask(yes="Give it a {item Item.Meat}", no="Keep it"):
            take(Item.Meat)
            say("Finally, someone who understands food.")
            send_to_city(line="Kiwimon joined the city!", species=Species.Kiwimon)
    else:
        say("No? Then come back with a {item Item.Meat}. I'll be here. I told you, I'm not moving.")
