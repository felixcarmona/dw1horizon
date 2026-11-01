# Grey Lord's Mansion 56, Soulmon's gallery, at night only (the brief's 60 reads no NPC list): Phantomon carries things for
# those who no longer need them. A fight at the Mansion's strength. Its home is the Secret Item Shop (city/secret-item-shop.py).
from dw import *

gallery = screen(Screen.grey_lords_mansion_56)
phantomon = gallery.npc(Species.Phantomon, at=(-500, -400), hp=1500, mp=2800, offense=470, defense=250, speed=130, brain=250, bits=700,
                        range=0, still=True, when=not recruited(Species.Phantomon) and clock.hour >= 20)


@phantomon.on_talk
def talk():
    say("I carry things for those who no longer need them.")
    if fight(phantomon) == "won":
        say("Your name stays on my list a little longer. Do you have a shop for me?")
        send_to_city(line="Phantomon joined the city!", species=Species.Phantomon)
