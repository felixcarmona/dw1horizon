# The Arena lobby, both of its screens: 208 until the ending, 223 after it (every way in loads 223 once engine.game_beaten is
# set, and there Airdramon and MetalGreymon stand beside Greymon). Kotemon (Ogre Fortress) trains here by day once beaten where
# it swings alone; Myotismon keeps the lobby at night after R2, on both screens. Kotemon stands on 208 only: 223 has no heap for
# its 87 KB model next to Airdramon and MetalGreymon (195 KB needed, 192 KB free), so after the ending it is not in the lobby.
# Kotemon offers a spar, as often as asked (100 bits a win, 150 with the battle bonus; less than a wild fight). A battle starts
# only once every bystander on screen has walked off it (BTL_handleBattleIntro): Greymon behind its desk cannot, and the lobby's
# battles never began; Greymon steps out for the spar, and the spar ends by loading the screen again at entry 2 (clear of
# Kotemon, on no step tile), which puts Greymon back at its desk. Kotemon is the only resident here by day, so no never-spawned
# NPC is sent off (leave() on one crashes).
from dw import *
from dw.base.arena_lobby_208 import lobby_208 as lobby208, greymon as greymon208
from dw.base.arena_lobby_223 import lobby_223 as lobby223, greymon as greymon223
from ..state import root2

# Keep its body box clear of entry 2 at (482, 165), the desk and the route to the door.
kotemon208 = lobby208.npc(Species.Kotemon, at=(850, -650), behaves_like=greymon208, bits=100, when=recruited(Species.Kotemon) and clock.hour < 20)
# Myotismon's body box (radius 250 + the tamer's 100) must stay off the player's first walks after the lobby loads: a player who
# crosses the floor before the model is drawn stands inside it, and an overlapping tamer cannot move again. At (0, 400) it sat on
# the way from the south door to the desk and to the arena stairs; here the box (x 600..1300, z -1350..-650) leaves every
# entry, the desk, the stairs and the doors clear, and the floor west of it stays open to talk.
myotismon208 = lobby208.npc(Species.Myotismon, at=(950, -1000), behaves_like=greymon208, when=root2 and clock.hour >= 20)
# After the ending, Myotismon on 223, whose floor is not 208's: tables stand where Kotemon stands on 208 ((850, -650) is a
# table tile there) and Airdramon stands at (1100, -1400). It takes the east corner between the tables and the wall: its box
# (x 800..1500, z -800..-100) leaves every entry, the desk, the stairs' step tiles, the doors and the open floor down the
# middle clear.
myotismon223 = lobby223.npc(Species.Myotismon, at=(1150, -450), behaves_like=greymon223, when=root2 and clock.hour >= 20)


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
def myotismon_talks():
    say("Good evening. The day belongs to the fighters; the night, to me.")
    say("I closed my collection. Now I study the living instead. Far more interesting, I find.")


@myotismon208.on_talk
def talk():
    myotismon_talks()


@myotismon223.on_talk
def talk():
    myotismon_talks()
