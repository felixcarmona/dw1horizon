# Native Forest 4: Floramon guards a seed that wants patience; a Sweet Nut wakes it (consumed, once). No fight. Its home
# is the Item Bank (city/item-keeper.py).
from dw import *

forest = screen(Screen.native_forest_4)
floramon = forest.npc(Species.Floramon, at=(2550, 800), range=0, when=not recruited(Species.Floramon))


@floramon.on_talk
def talk():
    say("Shh. This seed only opens for someone patient.")
    if has(Item.SweetNut):
        if ask(yes="Offer a {item Item.SweetNut}", no="Leave it be"):
            take(Item.SweetNut)
            say("It woke up! I'm taking it somewhere safe.")
            send_to_city(line="Floramon joined the city!", species=Species.Floramon)
    else:
        say("It likes sweet things. A {item Item.SweetNut} might wake it, if you ever find one.")
