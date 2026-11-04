# The Arena lobby (208; 223, where Airdramon and MetalGreymon stand, has no heap for Kotemon): Kotemon (Ogre Fortress) trains here
# by day once beaten where it swings alone; Myotismon keeps the lobby at night after R2. Kotemon offers a spar, as often as asked
# (100 bits a win, 150 with the battle bonus; less than a wild fight). A battle starts only once every bystander on screen has
# walked off it (BTL_handleBattleIntro): Greymon behind its desk cannot, and the lobby's battles never began; Greymon steps out
# for the spar, and the spar ends by loading the screen again at entry 2 (beside Kotemon, on no step tile), which puts Greymon
# back at its desk. Kotemon is the only resident here by day, so no never-spawned NPC is sent off (leave() on one crashes).
from dw import *
from dw.base.arena_lobby_208 import lobby_208 as lobby208, greymon as greymon208
from ..state import root2

kotemon208 = lobby208.npc(Species.Kotemon, at=(650, 250), behaves_like=greymon208, bits=100, when=recruited(Species.Kotemon) and clock.hour < 20)
myotismon208 = lobby208.npc(Species.Myotismon, at=(0, 400), behaves_like=greymon208, when=root2 and clock.hour >= 20)


@kotemon208.on_talk
def talk():
    say("A thousand swings at the Ogre Fortress, and you still beat me.", "So I teach here now, and I wait for a tournament day.")
    if ask(yes="Let's spar", no="Not now"):
        greymon208.leave()                # it always stands here; leave() needs an NPC that was spawned
        if fight(kotemon208) == "won":
            say("Good! Now back to my thousand swings. Come back whenever you want another round.")
        else:
            say("Your guard dropped. Come back stronger.")
        warp(Screen.arena_lobby_208, entry=2)    # Greymon is back at its desk (without it the desk's text has no speaker)


# Myotismon, with the Grey Lord at rest (R2, story-bible.md §3.4), moved to the city for good: it keeps the lobby at
# night, when Kotemon has gone (a night NPC and the day one never load together: the heap is the day's).
@myotismon208.on_talk
def talk():
    say("Good evening. The day belongs to the fighters; the night, to me.")
    say("I closed my collection. Now I study the living instead. Far more interesting, I find.")
