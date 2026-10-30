# 365, the Container House: the one real home of the Works. Psychemon, Shamamon and Tsukaimon share it, three who ran
# with the wrong crowds (the savanna, Trash Mountain, the Grey Lord's Mansion) until you beat them.
from dw import *

container_house = new_screen(365, map="build/what-the-island-forgot-maps/screens/BARR09.MAP")
psychemon = container_house.npc(Species.Psychemon, at=(-250, -450), range=0, when=recruited(Species.Psychemon))
shamamon = container_house.npc(Species.Shamamon, at=(300, -200), range=0, when=recruited(Species.Shamamon))
tsukaimon = container_house.npc(Species.Tsukaimon, at=(-300, 50), range=0, when=recruited(Species.Tsukaimon))


@psychemon.on_talk
def talk():
    say("We painted the round window ourselves.", "A box is a house once somebody waits for you in it.")


@shamamon.on_talk
def talk():
    roll = random.roll(3)
    if roll == 0:
        say("The bones say: a long road north, then a cold one. Bring meat.")
    elif roll == 1:
        say("The bones say: the city grows when you are not looking. Look anyway.")
    else:
        say("The bones say nothing today. Bones need rest too.")


@tsukaimon.on_talk
def talk():
    say("I used to keep watch for bad masters. Now I keep watch over this rug. Much better job.")
