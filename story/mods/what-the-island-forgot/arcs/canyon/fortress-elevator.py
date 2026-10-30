# Ogre Fortress, the elevator room (screen 48), §3.2 "After him or up": when Ogremon has ridden the escape elevator down,
# its second button is still lit. The chase is the first question at the elevator; "No use chasing him now" (the
# game's own words, made an option) closes it and the game's own menu follows (up to the canyon top, or not).
from dw import *
from dw.names import *
from dw.base.ogre_fortress_48 import fortress
from ...state import Canyon

@fortress.on_enter(when=ogre_fortress_cleared and Canyon.OPEN)
def band_cut_the_cable():
    # back in the room after leaving it: the band has cut the escape elevator's cable
    advance(Canyon.SETTLED)

@fortress.on_step(0, when=ogre_fortress_cleared and Canyon.OPEN)
def chase():
    tamer.say("The other button's still lit... That's where Ogremon went. Down.",
              "If we don't go now, they'll cut the cable.")
    if ask(yes="After him!", no="No use chasing him now"):
        advance(Canyon.CHASING)
        ride_down()
    else:
        advance(Canyon.SETTLED)

@fortress.on_step(0, when=Canyon.CHASING)
def down_again():
    if ask(yes="Ride it down", no="Not down there"):
        ride_down()

def ride_down():
    tamer.walk(1220, 3988, wait=False)
    partner.walk(1201, 3486, wait=False)
    tamer.arrived()
    partner.arrived()
    sound(8, 5)
    warp(302, entry=0)
