# 311, the Vault after "Stay" (R3): the wall is a curtain of water and Angemon keeps the door. The first time, the thaw is
# told; afterwards Angemon is the Sanctuary's visitable guardian, with the
# Record Keeper's hints (script 211, section 8: the library Angemon's talk in the city jumps to).
from dw import *
from ...state import root3

melted = new_screen(311, map="build/what-the-island-forgot-maps/screens/VALT02.MAP")
keeper = melted.npc(Species.Angemon, at=(0, 800), range=0, when=root3)
thaw_told = flag()

@melted.on_enter
def the_thaw():
    music(18)                     # the Ice Sanctuary's
    if not thaw_told:
        fade_from_white(2000)
        narrator.say("The wall of ice runs down as water.", "Far away, all over the island, something is remembered.")
        thaw_told.set()

@keeper.on_talk
def keeps_the_door():
    say("I keep the door now. If you ever lose your way, come and see me.")
    jump_to_script(211, 8)        # the Record Keeper's hints, as Angemon gives them in Jijimon's house
