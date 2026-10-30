# The Arena lobby (208, and 223 once Airdramon and MetalGreymon stand there): Fugamon (Misty Trees) and Hyogamon
# (Freezeland) train here by day once beaten where they live; Myotismon keeps the lobby at night after R2. One NPC per
# screen: the two screens of script 168 have different
# free slots. Hyogamon offers a spar, as often as asked (100 bits a win, less than a wild fight). A battle starts only once every bystander on screen has walked off it
# (BTL_handleBattleIntro): Greymon behind its desk cannot, and the lobby's battles never began; Greymon and Fugamon
# step out for the spar (they are back when the screen loads again).
from dw import *
from dw.base.arena_lobby_208 import lobby_208 as lobby208, greymon as greymon208
from dw.base.arena_lobby_223 import lobby_223 as lobby223, airdramon
from ..state import root2

fugamon208 = lobby208.npc(Species.Fugamon, at=(-600, 300), behaves_like=greymon208, when=recruited(Species.Fugamon) and clock.hour < 20)
hyogamon208 = lobby208.npc(Species.Hyogamon, at=(650, 250), behaves_like=greymon208, when=recruited(Species.Hyogamon) and clock.hour < 20)
myotismon208 = lobby208.npc(Species.Myotismon, at=(0, 400), behaves_like=greymon208, when=root2 and clock.hour >= 20)
fugamon223 = lobby223.npc(Species.Fugamon, at=(-600, 300), behaves_like=airdramon, when=recruited(Species.Fugamon))


def cousin():
    say("Ogremon's cousin, at your service!", "With no boss to follow, I train for the Arena now.",
        "Win the cups and maybe one day you can face me in the ring.")


@fugamon208.on_talk
def talk():
    return cousin()


@fugamon223.on_talk
def talk():
    return cousin()


@hyogamon208.on_talk
def talk():
    say("Freezeland made my fists hard as ice. You beat them anyway.", "Now I train here, waiting for a tournament day.")
    if ask(yes="Let's spar", no="Not now"):
        greymon208.leave()
        fugamon208.leave()
        if fight(hyogamon208) == "won":
            say("Hah! Good. Come back whenever you want another round.")
        else:
            say("Ice never melts. Come back stronger.")



# Myotismon, with the Grey Lord at rest (R2, story-bible.md §3.4), moved to the city for good: it keeps the lobby at
# night, when Fugamon and Hyogamon have gone (a night NPC and the day ones never load together: the heap is the day's).
@myotismon208.on_talk
def talk():
    say("Good evening. The day belongs to the fighters; the night, to me.")
    say("I closed my collection. Now I study the living instead. Far more interesting, I find.")
