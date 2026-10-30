# 247, Devimon on Mt. Infinity (script 194, §3.9): with R2 the Grey Lord's bones rest and Devimon's strings were cut
# before Analogman could pull them. Its scene is another: it pays its debt with a way up inside the mountain, straight
# to the Infinity Engine room (no Megadramon on that path), or lets the tamer climb. Marking the fight as done keeps the
# game's own scene from running after this one.
from dw import *
from dw.text import text
from dw.names import *
from ...state import root1, root2, root3, shortcut_taken

lib = script(194)                 # the library screen 247 runs (no screen of the Screen list)
devimon = entity(10)              # its slot 5
t53 = text.s194.sec53

@lib.on_step(2, when=root2 and not mt_infinity_devimon_beaten)
def pays_its_debt():
    devimon.say(t53.u0)
    devimon.play(28)
    raw.entity_move_to_axis(devimon, 0, 1, 20)        # it comes down, as in the game's own scene
    wait(3000)
    tamer.say(t53.u1)
    devimon.say("Easy, easy. You cut my strings before he could. Heh heh heh...", "I pay my debts.")
    devimon.say("There's a way up inside the mountain, straight to the room where he keeps his engine.",
                "Skip the climb. Megadramon won't even know you passed.")
    mt_infinity_devimon_beaten.set()
    if ask(yes="Take the shortcut", no="We'll climb"):
        devimon.say("Heh heh heh... Smart.")
        shortcut_taken.set()
        if root1 and root2 and root3:
            warp(313, entry=0)
        else:
            warp(312, entry=0)
    else:
        devimon.say("Heh heh heh... Suit yourself. I'll be watching.")
        devimon.leave()
