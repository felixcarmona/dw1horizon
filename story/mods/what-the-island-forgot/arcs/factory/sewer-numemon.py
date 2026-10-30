# 220, the sewer under Factorial Town (§3.5): with the Grey Lord at rest (R2) Giromon never went mad and no waste reached
# the sewer: Numemon is not sick, there is no battle, and the tamer talks him into the city, as Biyomon or Garurumon.
from dw import *
from dw.text import text
from dw.names import *
from dw.base.sewer_220 import sewer, numemon0, numemon1
from ...state import root2

t6 = text.s180.sec6

@sewer.on_enter(when=root2 and not sewer_fog_seen)
def clean_air():
    sewer_fog_seen.set()          # no waste, no smell: the game's scene of the fog (its section 52) does not play

@numemon0.on_talk(when=root2)
def feeling_fine():
    say("Bleh, bleh. Nice and quiet down here today.", "Somethin' was supposed to leak down here, but it never did.")

@numemon1.on_talk(when=root2 and not recruited(Species.Numemon), scene=True)
def talked_into_it():
    face(tamer)
    say("Bleh, bleh. Oh-ho? Visitors, down here?")
    tamer.say("You live in the sewer? Come to our city! There's sun, and food, and lots of friends.")
    say("Hmm... It's cozy down here, y'know. Damp. Dark. Perfect.")
    narrator.say("{player} tried hard to persuade him!")
    say("...Alright, alright! You sure talk a lot. Bleh, bleh.")
    tamer.say(t6.u10)
    say(t6.u11)
    walk_away(-137, 34, looks=6, pause=500)
    send_to_city(line=t6.u12, species=Species.Numemon, sound=(8, 10))
