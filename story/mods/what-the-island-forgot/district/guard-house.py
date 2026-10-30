# 359, the Guard House: the Works' watch post. Guardromon, Tankmon and SandYanmamon (the scout) move in once they have
# been beaten where they live (the game's own recruit on those wild fights: Factorial Town, the Toy Mansion, the Great
# Canyon); each stands there from then on.
from dw import *

guard_house = new_screen(359, map="build/what-the-island-forgot-maps/screens/BARR03.MAP")
guardromon = guard_house.npc(Species.Guardromon, at=(-500, -400), range=0, when=recruited(Species.Guardromon))
sandyanmamon = guard_house.npc(Species.SandYanmamon, at=(100, -700), range=0, when=recruited(Species.SandYanmamon))
tankmon = guard_house.npc(Species.Tankmon, at=(450, -500), range=0, when=recruited(Species.Tankmon))


@guardromon.on_talk
def talk():
    say("Factorial Town builds machines. I wanted to guard something that was not a machine.",
        "This post watches the stairs. Nobody comes up that I do not see.")


@tankmon.on_talk
def talk():
    if clock.hour >= 20 or clock.hour < 5:
        say("Night shift. The map on the wall is the whole island, every road you have walked.")
    else:
        say("Bang! ...That was practice. You knocked the shells out of me in the Toy Mansion,",
            "so now I keep them pointed at the sky.")


@sandyanmamon.on_talk
def talk():
    say("I scout the roads from the air and tell the others what comes.",
        "The canyon wind was full of sand. Up here it is only wind.")
