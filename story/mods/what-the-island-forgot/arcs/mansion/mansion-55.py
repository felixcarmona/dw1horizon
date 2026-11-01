# 55, the Grey Lord's Mansion, Myotismon's room (§3.4): with SkullGreymon kept, Myotismon can still close the circle later
# (R2, as "Let him rest" in the lab, lab.py). SkullGreymon stays in the city: only the circle closes.
from dw import *
from dw.names import *
from dw.base.grey_lords_mansion_55 import myotismon
from ...state import root2

@myotismon.on_talk(when=recruited(Species.SkullGreymon) and not root2)
def the_circle_can_close():
    say("The Grey Lord's circle is still open, boy.", "I can close it, and his house will let go.",
        "SkullGreymon will stay in your city either way.")
    if ask(yes="Close the circle", no="Not now"):
        say("...Yes. Come down to the basement, under the stairs, when you are ready.")
        root2.set()
        mansion_door_unlocked.s52_s55_exit4.set()
        mansion_door_unlocked.s52_s55_exit5.set()
        mansion_door_unlocked.s57_s58.set()
        mansion_door_unlocked.s53_s63.set()
        mansion_door_unlocked.s52_s59.set()
        mansion_door_unlocked.s53_s64.set()
        mansion_door_unlocked.s53_s232.set()
    else:
        return myotismon.talk()
